from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import os
import uuid
from database import init_db, get_children, get_section, add_section, update_section, delete_section, get_all_sections

app = Flask(__name__)
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx", "txt", "zip", "rar", "png", "jpg", "jpeg", "mp4"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/sections")
def api_sections():
    parent_id = request.args.get("parent_id")
    if parent_id in ("null", "", "0", None):
        parent_id = None
    else:
        parent_id = int(parent_id)
    sections = get_children(parent_id)
    return jsonify(sections)

@app.route("/api/tree")
def api_tree():
    sections = get_all_sections()
    return jsonify(sections)

@app.route("/api/sections", methods=["POST"])
def api_create_section():
    data = request.get_json()
    title = data.get("title")
    emoji = data.get("emoji", "")
    section_type = data.get("type", "folder")
    content = data.get("content")
    parent_id = data.get("parent_id")

    if parent_id in ("null", "", "0", None):
        parent_id = None
    else:
        parent_id = int(parent_id)

    new_id = add_section(title, emoji, section_type, content, parent_id)
    return jsonify({"id": new_id, "success": True})

@app.route("/api/sections/<int:section_id>", methods=["PUT"])
def api_update_section(section_id):
    data = request.get_json()
    title = data.get("title")
    emoji = data.get("emoji")
    content = data.get("content")
    update_section(section_id, title=title, emoji=emoji, content=content)
    return jsonify({"success": True})

@app.route("/api/sections/<int:section_id>", methods=["DELETE"])
def api_delete_section(section_id):
    count = delete_section(section_id)
    return jsonify({"success": True, "deleted": count})

@app.route("/api/upload", methods=["POST"])
def api_upload():
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No filename"}), 400
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(filepath)
        return jsonify({"path": filepath, "filename": filename})
    return jsonify({"error": "Invalid file type"}), 400

@app.route("/uploads/<path:filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    init_db()
    print("🌐 Web panel running at http://localhost:5000")
    print("📝 Open your browser and go to http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)
