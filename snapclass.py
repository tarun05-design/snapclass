import os
import shutil
from PIL import Image
import cv2
import face_recognition
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, jsonify, session
from sklearn.neighbors import KNeighborsClassifier
import joblib
from werkzeug.utils import secure_filename
import csv
from fpdf import FPDF
import pandas as pd
import mysql.connector
from datetime import datetime, timedelta
import uuid
import calendar
from urllib.parse import unquote

app = Flask(__name__)
app.secret_key = 'snapclass_simplified_2025'

# MySQL connection configuration
MYSQL_HOST =
MYSQL_USER =
MYSQL_PASSWORD =
MYSQL_DB =

# Global attendance set
att = set()

# Directories
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
MODELS_FOLDER = 'models'
DATASET_FOLDER = 'dataset'
TEMP_FOLDER = 'temp_uploads'

# Create necessary directories
for folder in [UPLOAD_FOLDER, PROCESSED_FOLDER, MODELS_FOLDER, DATASET_FOLDER, TEMP_FOLDER]:
    os.makedirs(folder, exist_ok=True)

# Static folder for serving processed images
os.makedirs('static/processed', exist_ok=True)
os.makedirs('static/temp', exist_ok=True)

# Database connection
def get_db_connection():
    try:
        connection = mysql.connector.connect(
            host=MYSQL_HOST,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB
        )
        return connection
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def get_attendance_history(class_name):
    """Get all attendance data for a class from database"""
    conn = get_db_connection()
    if not conn:
        return [], []

    cursor = conn.cursor()
    table_name = f"attendance_{class_name}"

    try:
        cursor.execute(f"DESCRIBE `{table_name}`")
        columns = cursor.fetchall()

        date_columns = []
        for column in columns:
            col_name = column[0]
            if col_name.startswith('d') and col_name != 'id' and len(col_name) > 2:
                try:
                    date_str = col_name[1:]
                    if len(date_str) >= 8:
                        day = date_str[:2]
                        month = date_str[2:4]  
                        year = date_str[4:8]

                        date_obj = datetime.strptime(f"{day}/{month}/{year}", "%d/%m/%Y")

                        date_columns.append({
                            'column_name': col_name,
                            'date_obj': date_obj,
                            'display_date': f"{day}/{month}/{year}",
                            'day_name': calendar.day_name[date_obj.weekday()]
                        })
                except:
                    continue

        date_columns.sort(key=lambda x: x['date_obj'], reverse=True)

        select_columns = ['name'] + [col['column_name'] for col in date_columns]
        query = f"SELECT {', '.join(f'`{col}`' for col in select_columns)} FROM `{table_name}`"
        cursor.execute(query)

        results = cursor.fetchall()

        attendance_table = []
        for row in results:
            student_data = {
                'name': row[0],
                'dates': {}
            }

            for i, date_col in enumerate(date_columns):
                col_index = i + 1
                if col_index < len(row):
                    raw_value = row[col_index]
                    student_data['dates'][date_col['column_name']] = 0 if raw_value is None else raw_value
                else:
                    student_data['dates'][date_col['column_name']] = 0

            attendance_table.append(student_data)

        cursor.close()
        conn.close()

        return attendance_table, date_columns

    except mysql.connector.Error as e:
        print(f"Database error: {e}")
        cursor.close()
        conn.close()
        return [], []

# Model generation
def model_gen(student_data, model_save_path, table_name):
    """Complete model generation with student data and database setup"""
    encodings = []
    labels = []

    # Create attendance table and insert student names
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()

        create_table_query = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            name VARCHAR(255) NOT NULL UNIQUE
        )"""
        cursor.execute(create_table_query)

        insert_query = f'INSERT IGNORE INTO `{table_name}` (name) VALUES (%s)'
        for student in student_data:
            cursor.execute(insert_query, (student['name'],))

        conn.commit()
        cursor.close()
        conn.close()

    # Process face recognition for each student
    for student in student_data:
        try:
            image_data = face_recognition.load_image_file(student['file_path'])
            face_locations = face_recognition.face_locations(image_data)
            face_encodings = face_recognition.face_encodings(image_data, face_locations)

            if len(face_encodings) == 0:
                print(f"No faces found in {student['file_path']}. Skipping...")
                continue

            encoding = face_encodings[0]
            encodings.append(encoding)
            labels.append(student['name'])
            print(f"Processed {student['name']}: Encoding shape - {encoding.shape}")

        except Exception as e:
            print(f"Error processing {student['file_path']}: {e}")
            continue

    if not encodings or not labels:
        raise ValueError("No valid encodings or labels found.")

    encodings = np.array(encodings)
    labels = np.array(labels)

    # Train KNN model
    knn_clf = KNeighborsClassifier(n_neighbors=min(2, len(labels)))
    knn_clf.fit(encodings, labels)

    # Save model
    with open(model_save_path, 'wb') as f:
        joblib.dump(knn_clf, f)
    print(f"Model saved at {model_save_path}")

# Process image for attendance
def process_image(image_path, model_path, table_name):
    try:
        knn_clf = joblib.load(model_path)
        model_student_names = list(knn_clf.classes_)

        frame = cv2.imread(image_path)
        if frame is None:
            return None, [], []

        face_locations = face_recognition.face_locations(frame)
        face_encodings = face_recognition.face_encodings(frame, face_locations)

        present_students = []

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            distances, indices = knn_clf.kneighbors([face_encoding], n_neighbors=1)
            label = indices[0][0]
            distance = distances[0][0]

            threshold = 0.5
            if distance <= threshold and label < len(model_student_names):
                name = model_student_names[label]
                present_students.append(name)
                att.add(name)
            else:
                name = "Unknown"

            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 3)

            label_size = cv2.getTextSize(name, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]
            cv2.rectangle(frame, (left, top - label_size[1] - 10), 
                         (left + label_size[0] + 10, top), (0, 255, 0), -1)

            cv2.putText(frame, name, (left + 5, top - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

        output_path = os.path.join('static/processed', os.path.basename(image_path))
        cv2.imwrite(output_path, frame)

        update_attendance_db_fixed(table_name, model_student_names, present_students)

        return output_path, model_student_names, present_students

    except Exception as e:
        print(f"Error processing image: {e}")
        return None, [], []

# Fixed attendance update
def update_attendance_db_fixed(table_name, all_students, present_students):
    """Fixed: Marks ALL students as either 0 (absent) or 1 (present)"""
    conn = get_db_connection()
    if not conn:
        return

    cursor = conn.cursor()

    try:
        today_date_column = datetime.today().strftime('d%d%m%Y')

        try:
            alter_query = f'ALTER TABLE `{table_name}` ADD COLUMN `{today_date_column}` TINYINT DEFAULT NULL'
            cursor.execute(alter_query)
        except mysql.connector.Error as e:
            if "Duplicate column name" not in str(e):
                print(f"Error: {e}")

        check_query = f'SELECT COUNT(*) FROM `{table_name}` WHERE `{today_date_column}` IS NOT NULL'
        cursor.execute(check_query)
        already_marked = cursor.fetchone()[0]

        if already_marked > 0:
            update_query = f'UPDATE `{table_name}` SET `{today_date_column}` = %s WHERE name = %s AND `{today_date_column}` IS NULL'
        else:
            update_query = f'UPDATE `{table_name}` SET `{today_date_column}` = %s WHERE name = %s'

        for student in all_students:
            attendance_value = 1 if student in present_students else 0
            cursor.execute(update_query, (attendance_value, student))

        conn.commit()

    except Exception as e:
        print(f"Database update error: {e}")
    finally:
        cursor.close()
        conn.close()

# Generate CSV and PDF functions
def generate_csv(class_name, all_students, present_students):
    try:
        today_date = datetime.today().strftime("%d/%m/%Y")

        with open('attendance.csv', 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['Name', today_date]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()

            for name in all_students:
                attendance_status = '1' if name in present_students else '0'
                writer.writerow({'Name': name, today_date: attendance_status})
    except Exception as e:
        print(f"Error generating CSV: {e}")

def generate_pdf(processed_image_paths, class_name):
    try:
        pdf = FPDF()
        pdf.set_auto_page_break(auto=False)

        pdf.add_page()
        pdf.set_font('Arial', 'B', 16)
        pdf.cell(0, 10, f'Attendance Report - {class_name}', 0, 1, 'C')

        today_formatted = datetime.today().strftime("%d/%m/%Y")
        pdf.cell(0, 10, f'Date: {today_formatted}', 0, 1, 'C')
        pdf.ln(10)

        for i, image_path in enumerate(processed_image_paths):
            if os.path.isfile(image_path):
                try:
                    image = Image.open(image_path)
                    img_width, img_height = image.size

                    page_width = pdf.w - 20
                    page_height = pdf.h - 40

                    scale = min(page_width / img_width, page_height / img_height)
                    new_width = img_width * scale * 0.264583
                    new_height = img_height * scale * 0.264583

                    x_offset = (pdf.w - new_width) / 2
                    y_offset = 30

                    pdf.add_page()
                    pdf.set_font('Arial', 'B', 12)
                    pdf.cell(0, 10, f'Group Photo {i+1}', 0, 1, 'C')

                    pdf.image(image_path, x=x_offset, y=y_offset, w=new_width, h=new_height)

                except Exception as e:
                    print(f"Error adding image: {e}")

        if hasattr(pdf, 'page') and pdf.page > 0:
            pdf.output("attendance_report.pdf")
    except Exception as e:
        print(f"Error generating PDF: {e}")

def delete_class_completely(class_name):
    try:
        model_path = os.path.join(MODELS_FOLDER, f"{class_name}.xml")
        if os.path.exists(model_path):
            os.remove(model_path)

        dataset_path = os.path.join(DATASET_FOLDER, class_name)
        if os.path.exists(dataset_path):
            shutil.rmtree(dataset_path)

        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            table_name = f"attendance_{class_name}"

            try:
                cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                conn.commit()
            except:
                pass
            finally:
                cursor.close()
                conn.close()

        return True
    except Exception as e:
        return False

# ROUTES
@app.route('/')
def home():
    try:
        return render_template('index.html')
    except:
        return """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>SNAPCLASS</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
                h1 { color: #4f46e5; text-align: center; margin-bottom: 30px; }
                .nav-links { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; }
                .nav-links a { background: #4f46e5; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; }
                .nav-links a:hover { background: #3730a3; }
                @media (max-width: 768px) { .nav-links { flex-direction: column; } .nav-links a { text-align: center; } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📸 SNAPCLASS</h1>
                <p style="text-align: center; color: #666; margin-bottom: 30px;">AI-Powered Attendance Management System</p>
                <div class="nav-links">
                    <a href="/view_classes">📋 View Classes</a>
                    <a href="/create_class">➕ Create Class</a>
                    <a href="/take_attendance">📷 Take Attendance</a>
                </div>
            </div>
        </body>
        </html>
        """

@app.route('/view_classes')
def view_classes():
    try:
        model_files = [f.split('.')[0] for f in os.listdir(MODELS_FOLDER) if f.endswith('.xml')]

        classes_info = []
        for class_name in model_files:
            dataset_path = os.path.join(DATASET_FOLDER, class_name)
            student_count = 0
            if os.path.exists(dataset_path):
                student_count = len([f for f in os.listdir(dataset_path) if f.endswith('.jpg')])
            classes_info.append({
                'name': class_name,
                'student_count': student_count
            })

        return render_template('view_classes.html', classes=classes_info)
    except Exception as e:
        flash(f"Error loading classes: {str(e)}")
        return redirect(url_for('home'))

@app.route('/delete_class/<path:class_name>', methods=['POST'])
def delete_class(class_name):
    try:
        class_name = unquote(class_name)

        if delete_class_completely(class_name):
            flash(f"✅ Class '{class_name}' deleted successfully.")
        else:
            flash(f"❌ Error deleting class.")

    except Exception as e:
        flash(f"❌ Error: {str(e)}")

    return redirect(url_for('view_classes'))

# SIMPLIFIED CREATE CLASS - 2 STEPS
@app.route('/create_class', methods=['GET', 'POST'])
def create_class():
    try:
        if request.method == 'POST':
            files = request.files.getlist('files')
            class_name = request.form.get('class_name')

            if not class_name:
                flash("❌ Please provide a class name.")
                return redirect(url_for('create_class'))

            if len(files) < 1 or not files[0].filename:
                flash("❌ Please upload at least one student photo.")
                return redirect(url_for('create_class'))

            # Check if class exists
            model_path = os.path.join(MODELS_FOLDER, f"{class_name}.xml")
            if os.path.exists(model_path):
                flash(f"❌ Class '{class_name}' already exists.")
                return redirect(url_for('create_class'))

            # Save uploaded files temporarily
            temp_files = []
            temp_class_folder = os.path.join(TEMP_FOLDER, f"class_{class_name}_{uuid.uuid4()}")
            os.makedirs(temp_class_folder, exist_ok=True)

            for i, file in enumerate(files):
                if file and file.filename:
                    temp_filename = f"student_{i+1}.jpg"
                    temp_filepath = os.path.join(temp_class_folder, temp_filename)
                    file.save(temp_filepath)

                    temp_files.append({
                        'temp_path': temp_filepath,
                        'original_name': file.filename,
                        'index': i + 1
                    })

            if not temp_files:
                flash("❌ No valid student photos found.")
                return redirect(url_for('create_class'))

            # Store in session for naming step
            session['temp_class_data'] = {
                'class_name': class_name,
                'temp_folder': temp_class_folder,
                'temp_files': temp_files
            }

            print(f"Session data stored: {session['temp_class_data']}")
            return redirect(url_for('name_students'))

        return render_template('create_class.html')
    except Exception as e:
        flash(f"Error in create class: {str(e)}")
        return redirect(url_for('view_classes'))

@app.route('/name_students', methods=['GET', 'POST'])
def name_students():
    try:
        print(f"Session data on name_students: {session.get('temp_class_data', 'NOT FOUND')}")

        if 'temp_class_data' not in session:
            flash("❌ No class creation in progress.")
            return redirect(url_for('create_class'))

        temp_data = session['temp_class_data']

        if request.method == 'POST':
            student_names = []

            for temp_file in temp_data['temp_files']:
                student_name = request.form.get(f'student_name_{temp_file["index"]}', '').strip()
                if student_name:
                    student_names.append({
                        'name': student_name,
                        'temp_path': temp_file['temp_path'],
                        'index': temp_file['index']
                    })

            if not student_names:
                flash("❌ Please provide names for at least one student.")
                return render_template('name_students.html', temp_data=temp_data)

            # Check for duplicate names
            names_set = set()
            for student in student_names:
                if student['name'] in names_set:
                    flash(f"❌ Duplicate student name: {student['name']}")
                    return render_template('name_students.html', temp_data=temp_data)
                names_set.add(student['name'])

            # Create class directly here
            class_name = temp_data['class_name']
            temp_folder = temp_data['temp_folder']

            # Create final class folder
            class_folder = os.path.join(DATASET_FOLDER, class_name)
            os.makedirs(class_folder, exist_ok=True)

            # Move and rename files with student names
            student_data = []
            for student in student_names:
                final_filename = f"{student['name']}.jpg"
                final_filepath = os.path.join(class_folder, final_filename)

                # Copy temp file to final location
                shutil.copy2(student['temp_path'], final_filepath)

                student_data.append({
                    'name': student['name'],
                    'file_path': final_filepath
                })

            try:
                # Generate model and create database table
                model_path = os.path.join(MODELS_FOLDER, f"{class_name}.xml")
                table_name = f"attendance_{class_name}"
                model_gen(student_data, model_path, table_name)

                # Clean up temp folder
                if os.path.exists(temp_folder):
                    shutil.rmtree(temp_folder)

                # Clear session
                session.pop('temp_class_data', None)

                flash(f"✅ Class '{class_name}' created with {len(student_data)} students!")
                return redirect(url_for('view_classes'))

            except Exception as e:
                flash(f"❌ Error creating class: {str(e)}")
                return render_template('name_students.html', temp_data=temp_data)

        return render_template('name_students.html', temp_data=temp_data)
    except Exception as e:
        flash(f"Error in name students: {str(e)}")
        return redirect(url_for('create_class'))

# COMPLETE ATTENDANCE FUNCTIONALITY
@app.route('/take_attendance', methods=['GET', 'POST'])
def take_attendance():
    try:
        if request.method == 'POST':
            files = request.files.getlist('files')
            class_name = request.form.get('class_name')

            if not class_name:
                flash("❌ Please select a class.")
                return redirect(url_for('take_attendance'))

            if not files or not files[0].filename:
                flash("❌ Please upload a group photo.")
                return redirect(url_for('take_attendance'))

            model_path = os.path.join(MODELS_FOLDER, f"{class_name}.xml")
            if not os.path.exists(model_path):
                flash("❌ Model not found for selected class.")
                return redirect(url_for('take_attendance'))

            att.clear()

            processed_images = []
            table_name = f"attendance_{class_name}"

            for file in files:
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    filepath = os.path.join(UPLOAD_FOLDER, filename)
                    file.save(filepath)

                    processed_image_path, model_student_names, present_students = process_image(
                        filepath, model_path, table_name)

                    if processed_image_path:
                        processed_images.append(processed_image_path)

            if not processed_images:
                flash("❌ Error processing images. Please try again.")
                return redirect(url_for('take_attendance'))

            generate_csv(class_name, model_student_names, list(att))
            generate_pdf(processed_images, class_name)

            attendance_table, attendance_dates = get_attendance_history(class_name)

            today_date = datetime.today().strftime("%d/%m/%Y")

            return render_template('attendance_result.html', 
                                 class_name=class_name,
                                 present_count=len(att),
                                 present_students=list(att),
                                 all_students=model_student_names,
                                 processed_images=processed_images,
                                 attendance_table=attendance_table,
                                 attendance_dates=attendance_dates,
                                 today_date=today_date)

        try:
            classes = [f.split('.')[0] for f in os.listdir(MODELS_FOLDER) if f.endswith('.xml')]
        except FileNotFoundError:
            classes = []

        return render_template('take_attendance.html', classes=classes)
    except Exception as e:
        flash(f"Error in take attendance: {str(e)}")
        return redirect(url_for('view_classes'))

@app.route('/download_csv')
def download_csv():
    try:
        if os.path.exists('attendance.csv'):
            return send_file('attendance.csv', as_attachment=True)
        else:
            flash("❌ No attendance report available.")
            return redirect(url_for('home'))
    except Exception as e:
        flash(f"Error downloading CSV: {str(e)}")
        return redirect(url_for('view_classes'))

@app.route('/download_pdf')
def download_pdf():
    try:
        if os.path.exists('attendance_report.pdf'):
            return send_file('attendance_report.pdf', as_attachment=True)
        else:
            flash("❌ No attendance report available.")
            return redirect(url_for('home'))
    except Exception as e:
        flash(f"Error downloading PDF: {str(e)}")
        return redirect(url_for('view_classes'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('view_classes'))

@app.errorhandler(500)
def internal_error(error):
    flash("An internal error occurred. Please try again.")
    return redirect(url_for('view_classes'))

if __name__ == '__main__':
    app.run(debug=True)
