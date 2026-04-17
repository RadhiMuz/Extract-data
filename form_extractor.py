import cv2
import pytesseract
import numpy as np
import json
import sys
from pdf2image import convert_from_path

# Point this to your Tesseract installation path
pytesseract.pytesseract.tesseract_cmd = r'C:\Users\protege\tesserect\tesseract.exe'

def preprocess_image(image_path):
    """Loads the image, converts to grayscale, and applies thresholding."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Apply binary thresholding. Adjust 150 if image is too dark/light
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY)
    
    return img, thresh

def extract_text_from_zone(thresh_img, x, y, w, h):
    """Crops the image and runs Tesseract OCR."""
    roi = thresh_img[y:y+h, x:x+w]
    
    # --- SAFETY CHECK ---
    # If the cropped box has a width or height of 0 (or is off-screen)
    if roi.size == 0:
        print(f"⚠️ ERROR: The box at [X:{x}, Y:{y}, W:{w}, H:{h}] is completely empty!")
        return ""
    
    # IMPORTANT: psm 6 tells Tesseract to assume a uniform block of text (perfect for columns)
    text = pytesseract.image_to_string(roi, config='--psm 6').strip()
    return text

def main():
    # Set this to your input file. MUST be a PDF.
    input_file = 'scanned_form.pdf' 
    
    # --- STRICT PDF-ONLY LOGIC ---
    if not input_file.lower().endswith('.pdf'):
        print(f"⚠️ ERROR: You provided '{input_file}'. This script now strictly requires a .pdf file!")
        sys.exit() # Stop the script immediately
        
    print(f"Detected PDF. Converting '{input_file}' to image...")
    image_path = 'temp_scanned_form.png'
    
    # ⚠️ CRITICAL: Change this path to match exactly where you put the Poppler 'bin' folder!
    poppler_dir = r'C:\Users\protege\Downloads\Release-25.12.0-0\poppler-25.12.0\Library\bin' 
    
    # Convert the PDF
    pages = convert_from_path(input_file, poppler_path=poppler_dir)
    pages[0].save(image_path, 'PNG')
    print("Conversion complete. Starting OCR...")
    
    # 1. Preprocess the image
    original_img, processed_img = preprocess_image(image_path)
    
    # 2. Define your Table Column Zones (Your exact numbers)
    zones = {
        "Grade": [131, 1216, 233, 95],
        "Thickness": [524, 1216, 158, 100],
        "Width": [711, 1212, 152, 100],
        "Length": [886, 1218, 151, 100],
        "Price_KG": [1057, 1214, 138, 100]
    }
    
    extracted_data = {}
    
    # 3. Extract Text Fields as Lists
    for column_name, coords in zones.items():
        x, y, w, h = coords
        
        # Get the raw block of text from the column
        raw_text = extract_text_from_zone(processed_img, x, y, w, h)
        
        # Split the text by line breaks (\n) to make a list
        clean_list = [line.strip() for line in raw_text.split('\n') if line.strip()]
        
        extracted_data[column_name] = clean_list
        
        # Draw a green rectangle on the original image for visual debugging
        cv2.rectangle(original_img, (x, y), (x + w, y + h), (0, 255, 0), 2)

    # 4. Output the results
    print("\n--- Extracted Table Columns ---")
    print(json.dumps(extracted_data, indent=4))
    
    # --- FIX: Proportional Resize for Display ---
    # Calculates a nice width (1200 pixels) and scales the height to match perfectly
    target_width = 1200
    aspect_ratio = original_img.shape[0] / original_img.shape[1] # height / width
    target_height = int(target_width * aspect_ratio)
    
    display_img = cv2.resize(original_img, (target_width, target_height)) 
    cv2.imshow('Debug Map', display_img)
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()