# FINAL IMPORTS
import sys
from flask import Flask, config, render_template, jsonify, request, session
from flask_apscheduler import APScheduler
from model.webloader import *
from model.sentinelcollection import *
from model.variablescollection import *
from model.model_loader import *
from model.db import *
from collections import defaultdict
import random 
import os
#from services.yield_analytics import *

app = Flask(__name__)
scheduler = APScheduler()
app.secret_key = os.environ["SECRET_KEY"]


if os.environ.get("AUTO_INIT_DB", "true").lower() == "true":
    try:
        initialize_database()
    except Exception as e:
        print(f"Database initialization skipped: {e}")


def try_generate_maps():
    """Generate map files when dependencies are ready, but do not block page load."""
    if os.environ.get("GENERATE_MAPS_ON_REQUEST") != "true":
        return

    map_jobs = [
        ("real-time map", create_map),
        ("historical maps", create_all_historical_maps),
        ("municipality maps", create_maps_per_municipality),
    ]

    for job_name, job in map_jobs:
        try:
            job()
        except Exception as e:
            print(f"Skipping {job_name}: {e}")


@scheduler.task('interval', id='sentinel_get', days=1)
def sentinel_get():

    print("\n\n\nSENTINEL WORKING\n\n\n")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(BASE_DIR, "static", "fields_coordinates.geojson")
    #filepath = os.path.join(os.getcwd(), "static", "fields_coordinates.geojson")
    
    # Sentinel acc ni Robby
    config = SHConfig()
    config.instance_id = os.environ["SENTINELHUB_INSTANCE_ID"]
    config.sh_client_id = os.environ["SENTINELHUB_CLIENT_ID"]
    config.sh_client_secret = os.environ["SENTINELHUB_CLIENT_SECRET"]

    ndvi_retriever = SentinelImageGet(filepath, config)

    municipality_polygons = ndvi_retriever.load_and_process_geojson()

    for city, polygons in municipality_polygons.items():
        ndvi_retriever.get_DateOfImage(city, polygons)

    ndvi_retriever.get_NDVI_Images(municipality_polygons)

    ndvi_images = ndvi_retriever.get_ndvi_images()
    selected_dates = ndvi_retriever.get_selected_dates()

    datafor_database = variableCollector(ndvi_images, selected_dates)
    datafor_database.extract_features()

    merged_data = datafor_database.get_merged_data() #ito gamitin for prediction

    cnn_model_instance = ModelLoader(merged_data)

    # Fit the scaler once on the merged dataset
    cnn_model_instance.fit_scaler()

#changes ni perl
@app.route('/handle_click', methods=['POST'])
def handle_click():
    data = request.get_json()  # Get the incoming JSON data
    municipality_clicked = data['municipality'].upper() #CHANGE 04-27
    year = data['year']
    season = data['season']
    yield_value = data['yield']

    session['municipality_clicked'] = municipality_clicked
    
    # Do something with the data (e.g., store it in a database, log it, etc.)
    print(f"Received data: {municipality_clicked}, {year}, {season}, {yield_value}")
    
    
    return jsonify({'status': 'success', 'message': 'Data received successfully'})
    #return redirect(url_for('view'))

@app.route('/get_real_time_data')
def get_real_time_data():
    """Fetch real-time yield data dynamically via AJAX."""
    try:
        municipalities, yields, yield_data = get_realtime_yield_data()  # ✅ Correctly unpacking 3 values

        print("✅ Real-time Data Fetched:", municipalities, yields, yield_data)  # Debugging Output

        response = jsonify({
            "municipalities": municipalities,
            "yields": yields,
            "yield_data": yield_data  # ✅ Include yield_data in JSON response
        })
        #print("🔹 JSON Response:", response.get_data(as_text=True))  # Debugging output
        return response

    except Exception as e:
        print(f"❌ Error fetching real-time data: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def home():
    try_generate_maps()
    return render_template('HomePage.html')

# Zoe's Dashboard Update
@app.route("/dashboard")
def dashboard():
    try:
        municipalities, real_time_yields, real_time_yield_data = get_realtime_yield_data()  #Unpacking three values ✅ 
    except Exception as e:
        print("❌ Error in get_realtime_yield_data:", e)
        municipalities, real_time_yields, real_time_yield_data = [], [], {}
    
    try:
        historical_yield_data = get_historical_data()
    except Exception as e:
        print("❌ Error in get_historical_data:", e)
        historical_yield_data = []
    municipality_clicked = session.get('municipality_clicked','')  # Default to 'Not clicked' if not found

    #yearly_trends = process_yearly_trends(historical_yield_data)
    #municipality_averages = process_municipality_averages(historical_yield_data)
    #seasonal_data = process_seasonal_yield(historical_yield_data)

    return render_template(
        "dashboard.html",
        # Pass the real-time yield data to the template
        municipalities=municipalities,
        real_time_yields=real_time_yields,
        real_time_yield_data=real_time_yield_data,

        # Pass the historical yield data to the template
        historical_yield_data=historical_yield_data,
        municipality_clicked=municipality_clicked
        #yearly_trends=yearly_trends,
        #municipality_averages=municipality_averages,
        #seasonal_data=seasonal_data,
    )

def get_color_for_muni(muni):
        random.seed(muni)  
        r = random.randint(50, 200)
        g = random.randint(50, 200)
        b = random.randint(50, 200)
        solid = f'rgba({r}, {g}, {b}, 1)'
        faded = f'rgba({r}, {g}, {b}, 0.5)'  
        return solid, faded

@app.route("/multi_year")
def multi_year():
    season = request.args.get("season")
    municipalities = request.args.getlist("municipality")

    # Convert season to int or None
    try:
        season = int(season) if season else None
    except ValueError:
        season = None

    try:
        all_munis = get_all_municipalities()
    except Exception as e:
        print("❌ Error in get_all_municipalities:", e)
        all_munis = []

    if not municipalities:
        municipalities = all_munis[:5]

    # Always fetch all season data to allow conditional processing
    try:
        historical_data = get_multi_year(season=None, municipalities=municipalities)
    except Exception as e:
        print("❌ Error in get_multi_year:", e)
        historical_data = []

    # chart_data[municipality][season][year] = yield
    chart_data = defaultdict(lambda: defaultdict(lambda: defaultdict(float)))
    years_set = set()

    for row in historical_data:
        municipality = row['municipality']
        year = row['year']
        season_val = row['season']
        yield_value = row['yield']

        chart_data[municipality][season_val][year] += yield_value
        years_set.add(year)

    sorted_years = sorted(years_set)
    formatted_chart_data = []

    for municipality, seasons in chart_data.items():
        color_solid, color_faded = get_color_for_muni(municipality)

        if season:  # Single season selected
            year_data = seasons.get(season, {})
            dataset = {
                'label': f"{municipality} - Season {season}",
                'data': [year_data.get(year, 0) for year in sorted_years],
                'fill': False,
                'borderColor': color_solid if season == 1 else color_faded,
                'backgroundColor': color_solid if season == 1 else color_faded,  
                'borderDash': [] if season == 1 else [5, 5],
                'tension': 0,
                'borderWidth': 2
            }
            formatted_chart_data.append(dataset)

        else:  # All seasons
            for season_val in [1, 2]:
                year_data = seasons.get(season_val, {})
                dataset = {
                    'label': f"{municipality} - Season {season_val}",
                    'data': [year_data.get(year, 0) for year in sorted_years],
                    'fill': False,
                    'borderColor': color_solid if season_val == 1 else color_faded,
                    'backgroundColor': color_solid if season_val == 1 else color_faded,  # <- Add this
                    'borderDash': [] if season_val == 1 else [5, 5],
                    'tension': 0,
                    'borderWidth': 2
                }
                formatted_chart_data.append(dataset)

    return render_template(
        "multi_year.html",
        years=sorted_years,
        chart_datasets=formatted_chart_data,
        selected_season=str(season) if season else '',
        municipalities=all_munis,
        selected_municipalities=municipalities
    )

@app.route('/view')
def view():

    try:
        municipalities, yields, yield_data = get_realtime_yield_data()  #Unpacking three values ✅ 
    except Exception as e:
        print("❌ Error in get_realtime_yield_data:", e)
        municipalities, yields, yield_data = [], [], {}

    try:
        yield_chart = generate_yield_chart(municipalities, yields) if municipalities and yields else None
    except Exception as e:
        print("❌ Error in generate_yield_chart:", e)
        yield_chart = None

    try:
        historical_yield_data = get_historical_data()
    except Exception as e:
        print("❌ Error in get_historical_data:", e)
        historical_yield_data = []
    
    # Get the clicked municipality data from the session
    municipality_clicked = session.get('municipality_clicked', 'Not clicked')  # Default to 'Not clicked' if not found

    # Pass the data to the template
    return render_template(
        'View.html', 
        municipalities=municipalities, 
        yields=yields, 
        yield_data=yield_data,  # Pass yield_data to template
        yield_chart=yield_chart,  
        table_container_id="yield-table-container",
        historical_yield_data=historical_yield_data,
        municipality_clicked=municipality_clicked,  # Add clicked data to template
    )



if __name__ == '__main__':
    scheduler.init_app(app)
    scheduler.start()
    app.run(debug=True)
