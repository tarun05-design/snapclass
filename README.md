# 📸 SNAPCLASS

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python)
![Flask](https://img.shields.io/badge/Flask-2.3-green?logo=flask)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Status](https://img.shields.io/badge/Status-Project_Active-brightgreen)

SNAPCLASS is an **AI-powered attendance management system** that simplifies and automates attendance using **facial recognition**.  
Built with Flask, it helps educators create classes, name students, take attendance from group photos, and generate transparent reports with ease.

---

## 🚀 Features
- 📂 **Class Creation** – Upload multiple student photos and assign names.  
- 🤖 **Automated Attendance** – Detect and mark students from group photos using face recognition.  
- 📊 **Reports** – Export attendance records as **CSV** or **PDF**.  
- 💻 **Responsive Web Interface** – Works seamlessly on desktop and mobile.  
- 🧩 **Step-by-Step Workflow** – Easy class creation and management process.  

---

## 📁 Project Structure

```
snapclass/
│
├── snapclass.py          # Flask backend main application
├── requirements.txt      # Python dependencies
├── README.md             # Project documentation
├── .gitignore            # Git ignore rules
│
├── templates/            # HTML templates for Flask
│   ├── base.html
│   ├── create_class.html
│   ├── name_students.html
│   ├── view_classes.html
│   ├── take_attendance.html
│   ├── attendance_result.html
│   └── ...additional templates
│
├── static/               # Static assets like CSS, JS, images
│   ├── temp/
│   ├── processed/
```

---

## ⚙️ Installation

1. **Clone the repo**
   ```bash
   git clone https://github.com/yourusername/snapclass.git
   cd snapclass
   ```

2. **Create and activate a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Linux/Mac
   venv\Scripts\activate      # On Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

---

## ▶️ Usage

Run the Flask app locally:

```bash
python snapclass.py
```

Then open your browser and go to:  
👉 `http://localhost:5000`

---

## ⚠️ Important Notes
- 🔑 **Credentials & Config** – Do **not** hardcode DB credentials. Use environment variables or config files.  
- 🔒 **Privacy** – Uploaded photos and datasets are excluded from the repo.  
- 🗄️ **Database** – Configure MySQL credentials properly in your environment before deployment.  

---

## 🤝 Contributing
Contributions and bug fixes are welcome!  

1. Fork the repository  
2. Create a feature branch (`git checkout -b feature-xyz`)  
3. Commit changes (`git commit -m 'Add new feature'`)  
4. Push to branch (`git push origin feature-xyz`)  
5. Submit a pull request 🎉  

---

## 📜 License
This project is licensed under the [MIT License](LICENSE).  
© 2025 SnapClass Team


---

👨‍💻 *Created as a final year AI/Data Science project for **Smart India Hackathon (SIH) 2025***.
