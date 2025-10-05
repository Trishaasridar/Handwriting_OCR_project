from flask import Flask, render_template, request, jsonify
from paddleocr import PaddleOCR
import os
from datetime import datetime
import tempfile
import mysql.connector
import base64

# Initialize Flask
app = Flask(__name__, template_folder='.')

# Initialize OCR once
# NOTE: This line requires PaddleOCR to be installed and models to be downloaded.
# It's kept as is from your original code.
ocr = PaddleOCR(lang="en", ocr_version="PP-OCRv4", use_angle_cls=True)

# ✅ MySQL connection details
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "1234",
    "database": "ocr"
}

def run_ocr(image_path):
    """Run OCR and return structured text."""
    result = ocr.predict(image_path)
    # The result structure from paddleocr.predict(image_path) varies by version.
    # The provided original code assumes a specific structure (result[0]["rec_boxes"]).
    # If the provided structure is not found, a safer approach is needed, 
    # but for compatibility, the original logic is retained.
    if not result or not result[0] or 'rec_boxes' not in result[0]:
         # Attempt a simpler extraction if the detailed structure is missing
        if result and result[0] and result[0][0]:
            return "\n".join([line[1] for line in result[0][0]]) if isinstance(result[0][0], list) else str(result)
        return "OCR failed to produce structured text."
    
    rec_boxes = result[0]["rec_boxes"]
    rec_texts = result[0]["rec_texts"]
    lines = list(zip(rec_boxes, rec_texts))
    lines.sort(key=lambda x: (x[0][1], x[0][0]))
    structured_lines = []
    current_line = []
    y_threshold = 10

    for (box, text) in lines:
        if not current_line:
            current_line.append((box, text))
        else:
            prev_box = current_line[-1][0]
            if abs(box[1] - prev_box[1]) < y_threshold:
                current_line.append((box, text))
            else:
                structured_lines.append(current_line)
                current_line = [(box, text)]
    if current_line:
        structured_lines.append(current_line)

    for line in structured_lines:
        line.sort(key=lambda x: x[0][0])

    final_text = "\n".join([" ".join([t for _, t in line]) for line in structured_lines])
    return final_text


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/process', methods=['POST'])
def process():
    """Process uploaded image and store in MySQL as BLOB."""
    try:
        student_name = request.form.get("studentName")
        course_name = request.form.get("courseName")
        file = request.files.get("handwrittenFile")

        if not file:
            return jsonify({"success": False, "message": "No file uploaded"})

        # Temporary save for OCR
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            # IMPORTANT: Reset file pointer to beginning before saving if it was read previously
            file.seek(0)
            file.save(tmp.name)
            image_path = tmp.name

        # OCR
        extracted_text = run_ocr(image_path)

        # Read binary data for DB storage
        with open(image_path, 'rb') as f:
            image_blob = f.read()

        os.remove(image_path)

        date_now = datetime.now().strftime("%Y-%m-%d")
        time_now = datetime.now().strftime("%H:%M:%S")

        # ✅ Store into MySQL
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ocr_results (student_name, course_name, image_blob, date, time, content)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_name, course_name, image_blob, date_now, time_now, extracted_text))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "success": True,
            "studentName": student_name,
            "courseName": course_name,
            "date": date_now,
            "time": time_now,
            "content": extracted_text
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

        
@app.route('/search', methods=['POST'])
def search():
    """Return all records from MySQL for the given student & course, paginated (8 per page: 4 left, 4 right)."""
    try:
        student_name = request.form.get("studentName", "").strip()
        course_name = request.form.get("courseName", "").strip()
        page = int(request.form.get("page", 1))
        # 💡 CHANGE: 4 results per column * 2 columns = 8 records per book page
        per_page = 8  

        # ✅ FIX: Check for empty search terms
        if not student_name and not course_name:
            # This should technically be caught by the front-end, but kept for robustness.
            return jsonify({"success": False, "message": "Please enter student name or course name."})

        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # ✅ Filter based on provided fields
        filters = []
        values = []
        if student_name:
            filters.append("student_name LIKE %s")
            values.append(f"%{student_name}%")
        if course_name:
            filters.append("course_name LIKE %s")
            values.append(f"%{course_name}%")

        # Build WHERE clause
        where_clause = "WHERE " + " AND ".join(filters) if filters else ""
        offset = (page - 1) * per_page

        # ✅ Total record count for pagination
        # Use placeholders for values to prevent SQL injection, even for COUNT
        count_query = f"SELECT COUNT(*) AS total FROM ocr_results {where_clause}"
        cursor.execute(count_query, values)
        total_records = cursor.fetchone()["total"]

        # ✅ Get filtered results (latest first)
        main_query = f"""
            SELECT id, student_name, course_name, image_blob, date, time, content FROM ocr_results
            {where_clause}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """
        # Values for the main query include search terms + LIMIT/OFFSET
        main_values = values + [per_page, offset]
        
        cursor.execute(main_query, main_values)
        records = cursor.fetchall()

        cursor.close()
        conn.close()

        if not records:
            return jsonify({"success": False, "message": "No records found for the given name/course."})

        # ✅ Convert datetime & image blob fields
        for r in records:
            # Handle date/time objects safely
            r["date"] = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], datetime) else str(r["date"])
            r["time"] = r["time"].strftime("%H:%M:%S") if isinstance(r["time"], datetime) else str(r["time"])
            
            # Convert BLOB to Base64
            r["image"] = base64.b64encode(r["image_blob"]).decode("utf-8")
            del r["image_blob"]

        total_pages = (total_records + per_page - 1) // per_page

        return jsonify({
            "success": True,
            "records": records,
            "page": page,
            "total_pages": total_pages,
            "total_records": total_records
        })

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


if __name__ == '__main__':
    app.run(debug=True)