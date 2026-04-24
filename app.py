import cv2
import pytesseract
import numpy as np
import pandas as pd
import streamlit as st
import os
from pdf2image import convert_from_path

# --- CONFIGURATION ---
#pytesseract.pytesseract.tesseract_cmd = r'C:\Users\protege\tesserect\tesseract.exe'
#poppler_dir = r'C:\Users\protege\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin' 

st.set_page_config(page_title="Namicoh OCR Form Extractor", layout="wide")

def preprocess_image(image_path):
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Gaussian Blur + Otsu's thresholding handles blurry/uneven scans better
    blurred = cv2.GaussianBlur(gray, (3, 3), 0)
    _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return img, thresh

def extract_text_from_zone(thresh_img, x, y, w, h, is_numeric=False):
    # Prevent out-of-bounds errors
    img_h, img_w = thresh_img.shape
    if y >= img_h or x >= img_w:
        return ""
    
    h = min(h, img_h - y)
    w = min(w, img_w - x)
    
    roi = thresh_img[y:y+h, x:x+w]
    if roi.size == 0:
        return ""
    
    # Upscale by 200% to catch tiny decimals
    roi_enlarged = cv2.resize(roi, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    
    # Apply different rules based on the column type
    if is_numeric:
        # STRICT WHITELIST: Only numbers and decimals allowed
        my_config = r'--psm 6 -c tessedit_char_whitelist=0123456789./'
    else:
        # LOOSE WHITELIST: Letters, numbers, and hyphens for Specifications
        my_config = r'--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./'
        
    text = pytesseract.image_to_string(roi_enlarged, config=my_config).strip()
    return text

# --- MAIN APP UI ---
st.title("📄 Supplier Form Auto-Extractor")
st.markdown("Upload a physical form to automatically extract the table data into a spreadsheet.")

# --- DROPDOWN SELECTION ---
form_orientation = st.selectbox(
    "Select Form Orientation:",
    options=["Portrait", "Landscape"],
    index=0 # Defaults to Portrait
)

uploaded_file = st.file_uploader("Upload Form (PDF, PNG, JPG)", type=['pdf', 'png', 'jpg'])

if uploaded_file is not None:
    temp_file_ext = uploaded_file.name.split('.')[-1]
    temp_filepath = f"temp_upload.{temp_file_ext}"
    
    with open(temp_filepath, "wb") as f:
        f.write(uploaded_file.getbuffer())
        
    image_path = 'temp_scanned_form.png'

    # --- NEW MULTI-PAGE LOGIC ---
    if temp_filepath.lower().endswith('.pdf'):
        with st.spinner('Reading PDF document...'):
            pages = convert_from_path(temp_filepath, ) #poppler_path=poppler_dir)
            total_pages = len(pages)
            
        # If the PDF has multiple pages, show the page selector
        if total_pages > 1:
            # Smart rule: Default to page 2 if Landscape is chosen
            default_page = 2 if (form_orientation == "Landscape" and total_pages >= 2) else 1
            
            selected_page = st.number_input(
                f"Select Page to Extract (This document has {total_pages} pages):", 
                min_value=1, 
                max_value=total_pages, 
                value=default_page
            )
            # Python counts from 0, so Page 1 is index 0, Page 2 is index 1
            page_index = selected_page - 1 
        else:
            st.info("Single page PDF detected.")
            page_index = 0
            
        # Save ONLY the specific page the user selected
        pages[page_index].save(image_path, 'PNG')
        
    else:
        # If it's just an image (PNG/JPG), pass it straight through
        image_path = temp_filepath

    # --- AI EXTRACTION LOGIC ---
    with st.spinner('Running AI Extraction...'):
        original_img, processed_img = preprocess_image(image_path)
        
        # CONDITIONAL COORDINATES
        if form_orientation == "Portrait":
            # Your existing working portrait coordinates
            zones = {
                "specification": {"coords": [120, 1210, 220, 100], "is_numeric": False},
                "Thickness":     {"coords": [550, 1200, 120, 110], "is_numeric": True},
                "Width":         {"coords": [700, 1210, 150, 110], "is_numeric": True},  
                "Price_KG":      {"coords": [1050, 1210, 135, 110], "is_numeric": True} 
            }
        else:
            # PLACEHOLDER landscape coordinates. Update these [x, y, w, h] later!
            zones = {
                "specification": {"coords": [280, 925, 385, 150], "is_numeric": False},
                "Thickness":     {"coords": [285, 830, 385, 50], "is_numeric": True},
                "Width":         {"coords": [285, 770, 385, 50], "is_numeric": True},  
                "Price_KG":      {"coords": [290, 290, 385, 90], "is_numeric": True} 
            }
        
        extracted_data = {}
        
        for column_name, info in zones.items():
            x, y, w, h = info["coords"]
            is_numeric = info["is_numeric"]
            
            raw_text = extract_text_from_zone(processed_img, x, y, w, h, is_numeric)
            
            clean_list = [line.strip() for line in raw_text.split('\n') if line.strip()]
            extracted_data[column_name] = clean_list
            
            cv2.rectangle(original_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    st.success("Extraction Complete!")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Scanned Document")
        rgb_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
        st.image(rgb_img, use_container_width=True)
        
    with col2:
        st.subheader("Extracted Data")
        
        max_length = 0
        for col_list in extracted_data.values():
            if len(col_list) > max_length:
                max_length = len(col_list)
                
        for col_name in extracted_data:
            while len(extracted_data[col_name]) < max_length:
                extracted_data[col_name].append("")
        
        try:
            df = pd.DataFrame(extracted_data)
            st.dataframe(df, use_container_width=True)
            
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download to CSV (Excel)",
                data=csv,
                file_name='extracted_supplier_data.csv',
                mime='text/csv',
            )
        except ValueError:
            st.error("⚠️ Unknown Error occurred while building the table.")
            st.json(extracted_data) 

    if os.path.exists(temp_filepath):
        os.remove(temp_filepath)
    if os.path.exists('temp_scanned_form.png'):
        os.remove('temp_scanned_form.png')
