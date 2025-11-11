import io
import os
import json
import pandas as pd
import geopandas as gpd
from flask import Flask, request, render_template_string, flash, redirect, url_for, send_file, session, Response
from dataretrieval import nwis
from pynhd import NLDI

# --- Configuration ---
STATION_LIST_DIR = 'stations'
STREAMFLOW_DIR = 'streamflows'
CATCHMENT_DIR = 'catchments'
EQUAL_AREA_CRS = "EPSG:5070"  # For accurate area calculation

# Initialize Flask App
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# --- Data Processing Helper Functions ---

def get_station_list(state_cd):
    """
    Fetches a list of stream gages for a state, processes datums, and returns a GeoDataFrame.
    """
    print(f"\n--- Searching for stations in {state_cd} with daily discharge data ---")
    try:
        sites_df = nwis.get_record(
            service='site',
            stateCd=state_cd,
            parameterCd='00060',  # Daily discharge
            hasDataTypeCd='dv'    # Has Daily Values
        )
    except Exception as e:
        print(f"ERROR: Could not retrieve site list from NWIS for state {state_cd}: {e}")
        return None

    if sites_df.empty:
        print(f"No sites found for state {state_cd} with the specified criteria.")
        return pd.DataFrame()

    print(f"Found {len(sites_df)} gages. Processing coordinate datums...")
    
    datum_to_epsg = {'NAD83': 'EPSG:4269', 'NAD27': 'EPSG:4267', 'WGS84': 'EPSG:4326'}
    reprojected_gdfs = []

    for datum, epsg in datum_to_epsg.items():
        subset = sites_df[sites_df['coord_datum_cd'] == datum]
        if not subset.empty:
            gdf = gpd.GeoDataFrame(
                subset,
                geometry=gpd.points_from_xy(subset['dec_long_va'], subset['dec_lat_va']),
                crs=epsg
            ).to_crs("EPSG:4326")
            reprojected_gdfs.append(gdf)

    if not reprojected_gdfs:
        print("Warning: No sites with recognized datums were found.")
        return pd.DataFrame()

    combined_gdf = pd.concat(reprojected_gdfs).reset_index(drop=True)
    combined_gdf['lon_wgs84'] = combined_gdf.geometry.x
    combined_gdf['lat_wgs84'] = combined_gdf.geometry.y
    
    print(f"Successfully processed and reprojected {len(combined_gdf)} stations to WGS84.")
    return combined_gdf[['site_no', 'station_nm', 'coord_datum_cd', 'lat_wgs84', 'lon_wgs84']]

# --- HTML Templates ---

# Main Page Template
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, shrink-to-fit=no">
    <title>USGS Local Data Downloader</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; background-color: #f4f4f9; }
        .container { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px; }
        h1, h2 { color: #0056b3; text-align: center; border-bottom: 2px solid #eee; padding-bottom: 10px; }
        h1 + p { text-align: center; color: #555; margin-top: -10px; margin-bottom: 30px; }
        form { display: flex; flex-direction: column; gap: 20px; }
        .form-group { display: flex; flex-direction: column; }
        label { font-weight: bold; margin-bottom: 5px; color: #555; }
        input[type="file"], input[type="date"], input[type="text"], select { padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-size: 16px; }
        input[type="submit"], button { background-color: #007bff; color: white; padding: 12px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; transition: background-color 0.3s; width: 100%; }
        input[type="submit"]:hover, button:hover { background-color: #0056b3; }
        .alert { padding: 15px; margin-top: 20px; border-radius: 4px; border: 1px solid transparent; }
        .alert-success { color: #155724; background-color: #d4edda; border-color: #c3e6cb; }
        .alert-danger { color: #721c24; background-color: #f8d7da; border-color: #f5c6cb; }
        .checkbox-group label { display: inline-block; margin-right: 20px; font-weight: normal; }
        .footer { text-align: center; margin-top: 30px; font-size: 0.9em; color: #777; }
    </style>
</head>
<body>
    <div class="container">
        <h1>USGS Data Downloader</h1>
        <p>A tool to find and download hydrologic data and catchment boundaries for USGS stream gages.</p>
        {% with messages = get_flashed_messages(with_categories=true) %}
          {% if messages %}
            {% for category, message in messages %}
              <div class="alert alert-{{ category }}">{{ message | safe }}</div>
            {% endfor %}
          {% endif %}
        {% endwith %}
    </div>

    <div class="container">
        <h2>Step 1: Download Station List (Optional)</h2>
        <p>Select a state to download a detailed CSV file of all active streamflow gages with daily data.
        <b>This will also create a <code>stations/stations.txt</code> file locally, ready for use in Step 2.</b></p>
        <form method="post">
            <div class="form-group">
                <label for="state_cd">Select State:</label>
                <select id="state_cd" name="state_cd" required>
                    {{ state_options|safe }}
                </select>
            </div>
            <button type="submit" name="action" value="download_stations">Download Station CSV</button>
        </form>
    </div>

    <div class="container">
        <h2>Step 2: Download Station Data</h2>
        <p>Upload a <code>.txt</code> file containing USGS station IDs (one per line) to download data locally.</p>
        <form method="post" enctype="multipart/form-data">
            <div class="form-group">
                <label for="station_file">Upload Station ID File (.txt):</label>
                <input type="file" id="station_file" name="station_file" accept=".txt" required>
            </div>

            <div class="form-group">
                <label>Choose Data Types to Download:</label>
                <div class="checkbox-group">
                    <label><input type="checkbox" name="data_type" value="streamflow"> Streamflow Data</label>
                    <label><input type="checkbox" name="data_type" value="catchment"> Catchment Area Data</label>
                </div>
            </div>

            <fieldset id="streamflow_options">
                <legend>Streamflow Options</legend>
                <div class="form-group">
                    <label><input type="checkbox" id="all_data_checkbox" name="all_data" value="true"> Download all available data</label>
                </div>
                <div class="form-group">
                    <label for="start_date">Start Date:</label>
                    <input type="date" id="start_date" name="start_date">
                </div>
                <div class="form-group">
                    <label for="end_date">End Date:</label>
                    <input type="date" id="end_date" name="end_date">
                </div>
                <div class="form-group">
                    <label for="parameter_cd">Parameter Code:</label>
                    <input type="text" id="parameter_cd" name="parameter_cd" value="00060" placeholder="e.g., 00060 for Discharge">
                    <small>Common codes: 00060 (Discharge, cfs), 00065 (Gage height, ft)</small>
                </div>
            </fieldset>
            
            <button type="submit" name="action" value="download_data">Start Local Download</button>
        </form>
    </div>

    <div class="footer">
        <p>Developed by Kshitij Dahal. Contact: <a href="mailto:geokshitij@gmail.com">geokshitij@gmail.com</a></p>
        <p>Powered by Flask, dataretrieval, and pynhd.</p>
    </div>

    <script>
        const allDataCheckbox = document.getElementById('all_data_checkbox');
        const startDateInput = document.getElementById('start_date');
        const endDateInput = document.getElementById('end_date');

        allDataCheckbox.addEventListener('change', function() {
            const isDisabled = this.checked;
            startDateInput.disabled = isDisabled;
            endDateInput.disabled = isDisabled;
            if (isDisabled) {
                startDateInput.value = '';
                endDateInput.value = '';
            }
        });
    </script>
</body>
</html>
"""

# Progress Page Template
PROGRESS_TEMPLATE = """
<!doctype html>
<html>
<head>
    <title>Download in Progress...</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 40px auto; padding: 0 20px; background-color: #f4f4f9; }
        .container { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #0056b3; }
        #progress-container { width: 100%; background-color: #e9ecef; border-radius: 4px; margin-bottom: 20px; }
        #progress-bar { width: 0%; height: 30px; background-color: #007bff; text-align: center; line-height: 30px; color: white; border-radius: 4px; transition: width 0.4s ease; }
        #log { height: 300px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; background-color: #f8f9fa; border-radius: 4px; white-space: pre-wrap; font-family: monospace; }
        .log-success { color: green; }
        .log-error { color: red; }
        .log-info { color: #555; }
        a.button { display: inline-block; margin-top: 20px; background-color: #28a745; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Download in Progress...</h1>
        <div id="progress-container">
            <div id="progress-bar">0%</div>
        </div>
        <div id="log"></div>
        <a href="/" class="button" id="done-button" style="display:none;">Go Back</a>
    </div>

    <script>
        const progressBar = document.getElementById('progress-bar');
        const log = document.getElementById('log');
        const doneButton = document.getElementById('done-button');

        function addLog(message, type = 'info') {
            const p = document.createElement('p');
            p.textContent = message;
            p.className = 'log-' + type;
            log.appendChild(p);
            log.scrollTop = log.scrollHeight; // Auto-scroll to bottom
        }

        const eventSource = new EventSource("/progress-stream");

        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);

            // Update progress bar
            progressBar.style.width = data.progress + '%';
            progressBar.textContent = Math.round(data.progress) + '%';

            // Add message to log
            if (data.message) {
                addLog(data.message, data.type || 'info');
            }

            // Check if process is finished
            if (data.progress >= 100) {
                progressBar.style.backgroundColor = '#28a745'; // Green for success
                addLog('--- All tasks complete! ---', 'success');
                doneButton.style.display = 'inline-block';
                eventSource.close();
            }
        };

        eventSource.onerror = function(err) {
            addLog('Connection to server lost. Process may have finished or an error occurred.', 'error');
            progressBar.style.backgroundColor = '#dc3545'; // Red for error
            doneButton.style.display = 'inline-block';
            eventSource.close();
        };
    </script>
</body>
</html>
"""

# --- State list for the dropdown ---
STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'FL': 'Florida', 'GA': 'Georgia',
    'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois', 'IN': 'Indiana', 'IA': 'Iowa',
    'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana', 'ME': 'Maine', 'MD': 'Maryland',
    'MA': 'Massachusetts', 'MI': 'Michigan', 'MN': 'Minnesota', 'MS': 'Mississippi',
    'MO': 'Missouri', 'MT': 'Montana', 'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire',
    'NJ': 'New Jersey', 'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina',
    'ND': 'North Dakota', 'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
    'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming'
}

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def index():
    state_options = "".join([f'<option value="{code}">{name}</option>' for code, name in STATES.items()])

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'download_stations':
            state_cd = request.form.get('state_cd')
            if not state_cd:
                flash("Please select a state.", 'danger')
                return redirect(url_for('index'))
            
            stations_df = get_station_list(state_cd)
            
            if stations_df is None or stations_df.empty:
                flash(f"No stations found for {STATES.get(state_cd, state_cd)} or an error occurred.", 'danger')
                return redirect(url_for('index'))

            os.makedirs(STATION_LIST_DIR, exist_ok=True)
            txt_filepath = os.path.join(STATION_LIST_DIR, 'stations.txt')
            stations_df['site_no'].to_csv(txt_filepath, index=False, header=False)
            flash(f"Successfully saved <code>stations/stations.txt</code> locally with {len(stations_df)} sites.", 'success')

            csv_buffer = io.StringIO()
            stations_df.to_csv(csv_buffer, index=False)
            mem = io.BytesIO(csv_buffer.getvalue().encode('utf-8'))
            mem.seek(0)
            
            return send_file(
                mem, as_attachment=True, download_name=f'{state_cd}_stations_wgs84.csv', mimetype='text/csv'
            )

        elif action == 'download_data':
            station_file = request.files.get('station_file')
            data_types = request.form.getlist('data_type')

            if not station_file or station_file.filename == '':
                flash("Please upload a station file.", 'danger')
                return redirect(url_for('index'))
            if not data_types:
                flash("Please select at least one data type to download.", 'danger')
                return redirect(url_for('index'))

            try:
                file_content = station_file.stream.read().decode("utf-8")
                sites = [line.strip() for line in file_content.splitlines() if line.strip()]
                if not sites:
                    flash("The uploaded file is empty.", 'danger')
                    return redirect(url_for('index'))
                session['sites'] = sites
            except Exception as e:
                flash(f"Error reading file: {e}", 'danger')
                return redirect(url_for('index'))

            session['data_types'] = data_types
            if 'streamflow' in data_types:
                use_all_data = request.form.get('all_data') == 'true'
                session['use_all_data'] = use_all_data
                if not use_all_data:
                    start_date = request.form.get('start_date')
                    end_date = request.form.get('end_date')
                    if not (start_date and end_date):
                        flash("Start and End dates are required unless 'All available data' is checked.", 'danger')
                        return redirect(url_for('index'))
                    session['start_date'] = start_date
                    session['end_date'] = end_date
                session['parameter_cd'] = request.form.get('parameter_cd', '00060')
            
            return redirect(url_for('progress_page'))

    return render_template_string(HTML_TEMPLATE, state_options=state_options)

@app.route('/progress')
def progress_page():
    return render_template_string(PROGRESS_TEMPLATE)

# ###########################################################################
# ############# CORRECTED SECTION STARTS HERE ###############################
# ###########################################################################

def process_downloads(sites, data_types, streamflow_params):
    """
    This is the generator function that performs the downloads and yields progress.
    It is now separate from the route and receives all necessary data as arguments.
    """
    total_steps = len(sites) * len(data_types)
    current_step = 0

    def send_update(message, type='info', step_increment=0):
        nonlocal current_step
        current_step += step_increment
        progress = (current_step / total_steps) * 100 if total_steps > 0 else 0
        data = {'progress': progress, 'message': message, 'type': type}
        yield f"data: {json.dumps(data)}\n\n"

    yield from send_update(f"Starting download for {len(sites)} sites...")

    if 'streamflow' in data_types:
        os.makedirs(STREAMFLOW_DIR, exist_ok=True)
        start_date = streamflow_params.get('start_date')
        end_date = streamflow_params.get('end_date')
        parameter_cd = streamflow_params.get('parameter_cd')
        
        for site_id in sites:
            try:
                df, _ = nwis.get_dv(sites=site_id, start=start_date, end=end_date, parameterCd=parameter_cd)
                if df.empty:
                    yield from send_update(f"WARNING: No streamflow data for site {site_id}.", 'info', 1)
                    continue
                
                filepath = os.path.join(STREAMFLOW_DIR, f'{site_id}.csv')
                df.to_csv(filepath)
                yield from send_update(f"SUCCESS: Saved streamflow for {site_id} to {filepath}", 'success', 1)
            except Exception as e:
                yield from send_update(f"ERROR: Failed streamflow for {site_id}: {e}", 'error', 1)

    if 'catchment' in data_types:
        os.makedirs(CATCHMENT_DIR, exist_ok=True)
        nldi = NLDI()
        for site_id in sites:
            try:
                basin_gdf = nldi.get_basins(site_id)
                if basin_gdf.empty:
                    yield from send_update(f"WARNING: No catchment found for site {site_id}.", 'info', 1)
                    continue

                gdf = basin_gdf.reset_index()
                gdf_proj = gdf.to_crs(EQUAL_AREA_CRS)
                area_sq_meters = gdf_proj.geometry.area.iloc[0]
                gdf['areasqkm'] = area_sq_meters / 1_000_000

                shapefile_path = os.path.join(CATCHMENT_DIR, f'USGS_{site_id}.shp')
                gdf.to_file(shapefile_path, driver='ESRI Shapefile')
                yield from send_update(f"SUCCESS: Saved catchment for {site_id} to {shapefile_path}", 'success', 1)
            except Exception as e:
                yield from send_update(f"ERROR: Failed catchment for {site_id}: {e}", 'error', 1)
    
    yield from send_update("--- FINISHED ---", 'success')

@app.route('/progress-stream')
def progress_stream():
    """
    This route function now reads from the session ONCE and passes the data
    to the generator. This keeps all session access within the request context.
    """
    sites = session.get('sites', [])
    data_types = session.get('data_types', [])
    
    streamflow_params = {}
    if 'streamflow' in data_types:
        if session.get('use_all_data'):
            streamflow_params['start_date'] = None
            streamflow_params['end_date'] = None
        else:
            streamflow_params['start_date'] = session.get('start_date')
            streamflow_params['end_date'] = session.get('end_date')
        streamflow_params['parameter_cd'] = session.get('parameter_cd')

    return Response(process_downloads(sites, data_types, streamflow_params), mimetype='text/event-stream')

# ###########################################################################
# ############# CORRECTED SECTION ENDS HERE #################################
# ###########################################################################

if __name__ == '__main__':
    for d in [STATION_LIST_DIR, STREAMFLOW_DIR, CATCHMENT_DIR]:
        os.makedirs(d, exist_ok=True)
    app.run(debug=True, port=5001)