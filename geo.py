import streamlit as st
import pandas as pd
import requests
import time
from io import BytesIO
import json
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import folium
from streamlit_folium import st_folium

# Page configuration
st.set_page_config(
    page_title="Jan Aushadhi Store Geocoder",
    page_icon="🏥",
    layout="wide"
)

st.title("🏥 Jan Aushadhi Store Geocoding App (Free Version)")
st.markdown("Upload an Excel file with store addresses and pin codes to get their latitude and longitude coordinates using free geocoding services.")

# Initialize geocoder
@st.cache_resource
def get_geocoder():
    return Nominatim(user_agent="jan_aushadhi_geocoder_v1.0")

# Function to clean and format address
def clean_address(address, pin_code):
    """Clean and format address for better geocoding results"""
    address = str(address).strip()
    pin_code = str(pin_code).strip()
    address = address.replace(',', ' ')
    address = ' '.join(address.split())
    return address, pin_code

# Function to geocode using multiple free services
def geocode_address_free(address, pin_code, delay=1):
    """
    Geocode an address using free services with multiple fallback strategies
    """
    try:
        clean_addr, clean_pin = clean_address(address, pin_code)
        address_formats = [
            f"{clean_addr} {clean_pin} India",
            f"{clean_addr}, {clean_pin}, India",
            f"{clean_addr} India {clean_pin}",
            f"{clean_addr}, India",
            f"{clean_pin}, India",
            clean_addr
        ]
        geocoder = get_geocoder()
        for addr_format in address_formats:
            try:
                time.sleep(delay)
                location = geocoder.geocode(addr_format, timeout=15, exactly_one=True)
                if location:
                    return {
                        'latitude': location.latitude,
                        'longitude': location.longitude,
                        'formatted_address': location.address,
                        'status': 'SUCCESS',
                        'service': 'Nominatim_Geopy'
                    }
            except (GeocoderTimedOut, GeocoderServiceError, Exception):
                continue
        return try_alternative_geocoder(clean_addr, clean_pin, delay)
    except Exception as e:
        return {'latitude': None, 'longitude': None, 'formatted_address': None, 'status': f"ERROR: {str(e)}", 'service': 'None'}

def try_alternative_geocoder(address, pin_code, delay=1):
    """
    Try multiple alternative free geocoding services
    """
    address_variants = [
        f"{address} {pin_code} India",
        f"{address}, {pin_code}, India",
        f"{address} India",
        f"{pin_code} India",
        address
    ]
    for variant in address_variants:
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {'q': variant, 'format': 'json', 'limit': 1, 'addressdetails': 1, 'countrycodes': 'in'}
            headers = {'User-Agent': 'Jan_Aushadhi_Geocoder/1.0 (Educational_Purpose)'}
            time.sleep(delay)
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    return {'latitude': float(result['lat']), 'longitude': float(result['lon']), 'formatted_address': result.get('display_name', ''), 'status': 'SUCCESS', 'service': 'Nominatim_HTTP'}
        except Exception:
            continue
    if pin_code and len(pin_code) >= 5:
        try:
            url = "https://nominatim.openstreetmap.org/search"
            params = {'postalcode': pin_code, 'country': 'India', 'format': 'json', 'limit': 1}
            headers = {'User-Agent': 'Jan_Aushadhi_Geocoder/1.0 (Educational_Purpose)'}
            time.sleep(delay)
            response = requests.get(url, params=params, headers=headers, timeout=15)
            if response.status_code == 200:
                data = response.json()
                if data:
                    result = data[0]
                    return {'latitude': float(result['lat']), 'longitude': float(result['lon']), 'formatted_address': f"Near {result.get('display_name', '')} (Pin Code: {pin_code})", 'status': 'SUCCESS', 'service': 'Nominatim_PostalCode'}
        except Exception:
            pass
    return {'latitude': None, 'longitude': None, 'formatted_address': None, 'status': 'ERROR: No results found', 'service': 'None'}

def create_map(df_successful):
    if df_successful.empty: return None
    center_lat = df_successful['Latitude'].mean()
    center_lon = df_successful['Longitude'].mean()
    m = folium.Map(location=[center_lat, center_lon], zoom_start=6, tiles='OpenStreetMap')
    for idx, row in df_successful.iterrows():
        popup_text = f"<b>Store Address:</b> {row.get(address_column, 'N/A')}<br><b>Pin Code:</b> {row.get(pincode_column, 'N/A')}<br><b>Coordinates:</b> {row['Latitude']:.6f}, {row['Longitude']:.6f}"
        folium.Marker(location=[row['Latitude'], row['Longitude']], popup=folium.Popup(popup_text, max_width=300), tooltip=f"Store: {row.get(address_column, 'N/A')[:30]}...", icon=folium.Icon(color='red', icon='plus', prefix='fa')).add_to(m)
    return m

# --- START OF UI LOGIC ---

with st.expander("ℹ️ About Free Geocoding & Usage"):
    st.markdown("""
    This app uses **OpenStreetMap Nominatim**, a free and powerful geocoding service.
    - ✅ **100% Free:** No API keys or costs required.
    - ⚠️ **Rate Limited:** To respect the free service policy, there's an automatic 1-second delay between requests. This means processing is slower but reliable.
    - 💡 **Tip:** For best results, ensure your addresses are as complete as possible (e.g., include city and state).
    """)

uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx', 'xls'], help="Upload an Excel file containing columns for Address and Pin Code")

# <<< KEY CHANGE 1: Initialize session_state when a new file is uploaded >>>
if uploaded_file:
    # When a new file is uploaded, reset the session state to clear old results
    if 'processed_df' not in st.session_state or st.session_state.get('file_name') != uploaded_file.name:
        st.session_state.processed_df = None
        st.session_state.file_name = uploaded_file.name

    try:
        df = pd.read_excel(uploaded_file)
        st.success(f"✅ File '{uploaded_file.name}' uploaded successfully! Found {len(df)} records.")
        st.subheader("📊 Uploaded Data Preview")
        st.dataframe(df.head())
        
        st.subheader("🗂️ Column Mapping")
        col1, col2 = st.columns(2)
        with col1:
            address_column = st.selectbox("Select Address Column", options=df.columns.tolist(), key='address_col')
        with col2:
            pincode_column = st.selectbox("Select Pin Code Column", options=df.columns.tolist(), key='pincode_col')
        
        st.subheader("⚙️ Processing Options")
        col1, col2 = st.columns(2)
        with col1:
            delay_seconds = st.slider("Delay between requests (seconds)", min_value=1, max_value=5, value=1, help="Longer delays are safer for large datasets.")
        with col2:
            max_records = st.number_input("Maximum records to process (0 = all)", min_value=0, max_value=len(df), value=0, help="Limit processing for testing.")

        if st.button("🌍 Start Free Geocoding", type="primary"):
            if address_column and pincode_column:
                st.subheader("🔄 Processing...")
                records_to_process = len(df) if max_records == 0 else min(max_records, len(df))
                df_to_process = df.head(records_to_process).copy()
                st.info(f"Processing {records_to_process} records with {delay_seconds}s delay. Please be patient!")
                
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                results = []
                for index, row in df_to_process.iterrows():
                    address = str(row[address_column]) if pd.notna(row[address_column]) else ""
                    pin_code = str(row[pincode_column]) if pd.notna(row[pincode_column]) else ""
                    if address and pin_code:
                        status_text.text(f"Processing {index + 1}/{records_to_process}: {address[:50]}...")
                        result = geocode_address_free(address, pin_code, delay_seconds)
                        results.append(result)
                    else:
                        results.append({'latitude': None, 'longitude': None, 'formatted_address': None, 'status': "ERROR: Missing address or pin", 'service': 'None'})
                    progress_bar.progress((index + 1) / records_to_process)
                
                progress_bar.empty()
                status_text.empty()
                
                # Create results dataframe and store it in session state
                results_df = pd.DataFrame(results)
                results_df.rename(columns={'latitude': 'Latitude', 'longitude': 'Longitude', 'formatted_address': 'Formatted_Address', 'status': 'Geocoding_Status', 'service': 'Geocoding_Service'}, inplace=True)
                
                # <<< KEY CHANGE 2: Store the processed dataframe in session_state >>>
                st.session_state.processed_df = pd.concat([df_to_process.reset_index(drop=True), results_df], axis=1)

                # Rerun to clear the button state and move to the display logic below
                st.rerun()

    except Exception as e:
        st.error(f"❌ Error reading or processing file: {e}")

# <<< KEY CHANGE 3: Display results IF they exist in session_state >>>
# This entire block is now OUTSIDE the button's "if" statement.
if st.session_state.get('processed_df') is not None:
    st.header("✅ Geocoding Complete!", divider='rainbow')
    
    df_results = st.session_state.processed_df
    
    # Summary statistics
    st.subheader("📊 Results Summary")
    col1, col2, col3, col4 = st.columns(4)
    successful = len(df_results[df_results['Geocoding_Status'] == 'SUCCESS'])
    failed = len(df_results) - successful
    success_rate = (successful / len(df_results)) * 100 if len(df_results) > 0 else 0
    col1.metric("Total Processed", len(df_results))
    col2.metric("Successfully Geocoded", successful)
    col3.metric("Failed", failed)
    col4.metric("Success Rate", f"{success_rate:.1f}%")

    # Display results table
    st.subheader("🗂️ Geocoded Data")
    st.dataframe(df_results)

    # Download section
    st.subheader("💾 Download & Preview Results")
    csv_output = df_results.to_csv(index=False).encode('utf-8')
    excel_output = BytesIO()
    with pd.ExcelWriter(excel_output, engine='openpyxl') as writer:
        df_results.to_excel(writer, index=False, sheet_name='Geocoded_Stores')
    excel_data = excel_output.getvalue()

    col1, col2 = st.columns(2)
    with col1:
        st.download_button(label="📥 Download as Excel (.xlsx)", data=excel_data, file_name="geocoded_results.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    with col2:
        st.download_button(label="📄 Download as CSV", data=csv_output, file_name="geocoded_results.csv", mime="text/csv")
    
    with st.expander("👀 Click to Preview Raw CSV Output"):
        st.code(csv_output.decode('utf-8'), language='csv')

    # Map visualization
    successful_df = df_results[df_results['Geocoding_Status'] == 'SUCCESS'].copy()
    if not successful_df.empty:
        st.subheader("🗺️ Store Locations Map")
        folium_map = create_map(successful_df)
        if folium_map:
            st_folium(folium_map, width=700, height=500, returned_objects=[])
            st.info(f"📍 Showing {len(successful_df)} successfully geocoded locations on the map.")
    else:
        st.warning("No addresses were successfully geocoded to display on the map.")

# Instructions if no file is uploaded yet
if not uploaded_file:
    st.info("👆 Please upload an Excel file to get started.")
    with st.expander("📋 Excel File Format Requirements"):
        st.markdown("Your Excel file must contain columns for **Address** and **Pin Code**.")

# Footer
st.markdown("---")
st.markdown("🏥 **Jan Aushadhi Store Geocoding App (Free Version)**")