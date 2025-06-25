import streamlit as st
import pandas as pd
import time
from io import BytesIO
from geopy.geocoders import Nominatim, ArcGIS
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import folium
from streamlit_folium import st_folium

# --- Page Configuration ---
st.set_page_config(
    page_title="Advanced Jan Aushadhi Geocoder",
    page_icon="🏥",
    layout="wide"
)

# --- App Title and Description ---
st.title("🏥 Advanced Jan Aushadhi Geocoder (State-Aware)")
st.markdown("Upload an Excel file and **select a state** to get highly accurate geocodes using a dual-service strategy.")

# --- Constants and Helper Functions ---
INDIAN_STATES = [
    "Select a State (Strongly Recommended)", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", 
    "Maharashtra", "Manipur", "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", 
    "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal", 
    "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", 
    "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"
]

@st.cache_resource
def get_nominatim_geocoder():
    return Nominatim(user_agent="jan_aushadhi_geocoder_streamlit_v2.4")

@st.cache_resource
def get_arcgis_geocoder():
    return ArcGIS(user_agent="jan_aushadhi_geocoder_streamlit_v2.4")

def clean_and_format_pincode(pin_code):
    if pd.isna(pin_code): return ""
    return str(pin_code).split('.')[0].strip()

def geocode_address(address, pin_code, state=None, delay=1.1):
    """Geocodes an address, prioritizing results within the given state."""
    clean_address = str(address).strip()
    clean_pin = clean_and_format_pincode(pin_code)
    
    if not clean_address and not clean_pin:
        return {'latitude': None, 'longitude': None, 'formatted_address': 'Missing Input', 'status': 'FAILED', 'service': 'None'}

    # Build a list of address formats to try, from most specific to least specific
    address_formats = []
    if state:
        # Prioritize queries that include the state
        address_formats.extend([
            f"{clean_address}, {clean_pin}, {state}, India",
            f"{clean_address}, {state}, India",
        ])
    # Add general queries as fallbacks
    address_formats.extend([
        f"{clean_address}, {clean_pin}, India",
        f"{clean_address}, India",
        f"{clean_pin}, India" if clean_pin else None
    ])
    address_formats = [addr for addr in address_formats if addr]

    geolocators = [
        {'name': 'Nominatim', 'geocoder': get_nominatim_geocoder()},
        {'name': 'ArcGIS', 'geocoder': get_arcgis_geocoder()}
    ]

    for service in geolocators:
        for addr_format in address_formats:
            try:
                if service['name'] == 'Nominatim':
                    time.sleep(delay)
                
                location = service['geocoder'].geocode(addr_format, timeout=10)
                
                if location:
                    return {
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'formatted_address': location.address,
                        'status': 'SUCCESS',
                        'service': service['name']
                    }
            except (GeocoderTimedOut, GeocoderServiceError, Exception):
                continue
    
    return {'latitude': None, 'longitude': None, 'formatted_address': 'Not Found', 'status': 'FAILED', 'service': 'None'}

def create_map(df_successful, address_col, pincode_col):
    """Creates a Folium map with markers for successfully geocoded locations."""
    if df_successful.empty: return None
    
    m = folium.Map(location=[df_successful['Latitude'].mean(), df_successful['Longitude'].mean()], zoom_start=7, tiles='CartoDB positron')
    
    for _, row in df_successful.iterrows():
        popup_html = f"""
        <b>Store:</b> {row.get(address_col, 'N/A')}<br>
        <b>Pin:</b> {row.get(pincode_col, 'N/A')}<br>
        <b>Found Address:</b> {row['Formatted_Address']}<br>
        <b>Service:</b> {row['Geocoding_Service']}
        """
        iframe = folium.IFrame(popup_html, width=300, height=100)
        popup = folium.Popup(iframe, max_width=300)
        icon_color = "blue" if row['Geocoding_Service'] == 'Nominatim' else "green"
        folium.Marker(location=[row['Latitude'], row['Longitude']], popup=popup, tooltip=str(row.get(address_col, 'Store'))[:50] + "...", icon=folium.Icon(color=icon_color, icon='hospital', prefix='fa')).add_to(m)
        
    return m

# --- UI LOGIC ---

with st.expander("ℹ️ How This Works & Usage Guide"):
    st.markdown("""
    - **State Selection is Key:** To avoid errors from similarly named locations, please select the state your data is from. This dramatically improves accuracy.
    - **Dual-Service Strategy:** Uses Nominatim first, then falls back to ArcGIS.
    - **Patience is key:** Processing 100 records takes about 2 minutes due to required delays.
    """)

st.subheader("1. Upload Your Excel File")
uploaded_file = st.file_uploader("Choose an Excel file (.xlsx, .xls)", type=['xlsx', 'xls'], label_visibility="collapsed")

if 'processed_df' not in st.session_state: st.session_state.processed_df = None
if 'file_name' not in st.session_state: st.session_state.file_name = None
if uploaded_file and uploaded_file.name != st.session_state.file_name:
    st.session_state.processed_df = None
    st.session_state.file_name = uploaded_file.name

if uploaded_file:
    try:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
        st.success(f"✅ File '{uploaded_file.name}' loaded successfully with {len(df)} rows.")
        
        st.subheader("2. Preview of Uploaded Data")
        st.dataframe(df.head())
        
        st.subheader("3. Configure Processing")
        col1, col2 = st.columns(2)
        with col1:
            address_column = st.selectbox("Select Address Column:", options=df.columns, index=0)
            pincode_col_index = 1 if len(df.columns) > 1 else 0
            pincode_column = st.selectbox("Select Pin Code Column:", options=df.columns, index=pincode_col_index)
        
        with col2:
            # --- NEW: State Selector ---
            selected_state = st.selectbox("Select State to Improve Accuracy:", options=INDIAN_STATES)
            
            default_records = min(100, len(df))
            max_records = st.number_input("Records to process (0=all):", min_value=0, max_value=len(df), value=default_records)

        if st.button("🌍 Start Geocoding", type="primary", use_container_width=True):
            # Pass the selected state to the processing logic
            state_to_use = selected_state if selected_state != INDIAN_STATES[0] else None
            
            records_to_process = len(df) if max_records == 0 else min(max_records, len(df))
            df_to_process = df.head(records_to_process).copy()
            
            st.info(f"🚀 Starting geocoding for {records_to_process} records. Please be patient...")
            
            progress_bar = st.progress(0, text="Initializing...")
            
            results = []
            for index, row in df_to_process.iterrows():
                progress = (index + 1) / records_to_process
                progress_bar.progress(progress, text=f"Processing row {index + 1}/{records_to_process}...")
                
                result = geocode_address(row.get(address_column), row.get(pincode_column), state=state_to_use)
                results.append(result)

            results_df = pd.DataFrame(results)
            results_df.rename(columns={'latitude': 'Latitude', 'longitude': 'Longitude', 'formatted_address': 'Formatted_Address', 'status': 'Geocoding_Status', 'service': 'Geocoding_Service'}, inplace=True)
            
            st.session_state.processed_df = pd.concat([df_to_process.reset_index(drop=True), results_df], axis=1)
            st.session_state.address_col_name = address_column
            st.session_state.pincode_col_name = pincode_column

            st.rerun()

    except Exception as e:
        st.error(f"❌ An error occurred: {e}")

if st.session_state.processed_df is not None:
    st.header("🏁 Geocoding Complete!", divider='rainbow')
    
    df_results = st.session_state.processed_df
    
    st.subheader("📊 Results Summary")
    successful = len(df_results[df_results['Geocoding_Status'] == 'SUCCESS'])
    success_rate = (successful / len(df_results) * 100) if len(df_results) > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Processed", len(df_results))
    col2.metric("✅ Success", successful)
    col3.metric("❌ Failed", len(df_results) - successful)
    col4.metric("Success Rate", f"{success_rate:.1f}%")
    
    if successful > 0:
        st.write("Service Usage Breakdown:")
        st.bar_chart(df_results[df_results['Geocoding_Status'] == 'SUCCESS']['Geocoding_Service'].value_counts())

    st.subheader("🗂️ Geocoded Data & Download")
    st.dataframe(df_results)

    excel_output = BytesIO()
    df_results.to_excel(excel_output, index=False, sheet_name='Geocoded_Data', engine='openpyxl')
    
    st.download_button(label="📥 Download Results as Excel", data=excel_output.getvalue(), file_name=f"geocoded_{st.session_state.file_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

    successful_df = df_results[df_results['Latitude'].notna()].copy()
    if not successful_df.empty:
        st.subheader("🗺️ Map of Geocoded Stores")
        folium_map = create_map(successful_df, st.session_state.address_col_name, st.session_state.pincode_col_name)
        st_folium(folium_map, use_container_width=True, height=500)
        st.info(f"Showing {len(successful_df)} stores. Blue markers = Nominatim, Green markers = ArcGIS.")
    else:
        st.warning("No locations were successfully geocoded to display on the map.")

st.markdown("---")
st.markdown("Developed with Streamlit | Geocoding by Nominatim (OpenStreetMap) & ArcGIS")
