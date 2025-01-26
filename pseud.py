import os
import sqlite3
from flask import Flask, request, redirect, url_for, session, abort, render_template
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY"  # Replace with your own secret key
app.config["UPLOAD_FOLDER"] = os.path.join("static", "pdfs")
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

DATABASE = "app.db"

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

# Create tables if they do not exist
with get_db_connection() as conn:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            owner_id INTEGER NOT NULL,
            FOREIGN KEY(owner_id) REFERENCES users(id)
        )
    """)


# -------------
#   Routes
# -------------

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        password_hash = generate_password_hash(password)

        with get_db_connection() as conn:
            try:
                conn.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                             (username, password_hash))
                conn.commit()
            except sqlite3.IntegrityError:
                return "Username already taken!"
        return redirect(url_for("login"))
    # GET
    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        with get_db_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            if user and check_password_hash(user["password_hash"], password):
                # Set session
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                return redirect(url_for("my_library"))
            else:
                return "Invalid credentials!"
    # GET
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/upload", methods=["GET", "POST"])
def upload():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        pdf_file = request.files.get("pdf_file")
        if pdf_file and pdf_file.filename.endswith(".pdf"):
            filename = secure_filename(pdf_file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            pdf_file.save(file_path)

            with get_db_connection() as conn:
                conn.execute("INSERT INTO books (filename, owner_id) VALUES (?, ?)",
                             (filename, session["user_id"]))
                conn.commit()

            return redirect(url_for("my_library"))
        else:
            return "Please upload a valid PDF file."
    # GET
    return render_template("upload.html")

@app.route("/my_library")
def my_library():
    if "user_id" not in session:
        return redirect(url_for("login"))

    with get_db_connection() as conn:
        books = conn.execute("SELECT * FROM books WHERE owner_id = ?", (session["user_id"],)).fetchall()
        users = conn.execute("SELECT username FROM users WHERE id != ?", (session["user_id"],)).fetchall()

    return render_template(
        "my_library.html",
        books=books,
        users=users,
        current_user=session.get("username")
    )

@app.route("/library/<username>")
def user_library(username):
    with get_db_connection() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if not user:
            return "User not found!"
        books = conn.execute("SELECT * FROM books WHERE owner_id = ?", (user["id"],)).fetchall()

    return render_template(
        "user_library.html",
        books=books,
        username=username
    )

@app.route("/pdf/<int:book_id>")
def view_pdf(book_id):
    with get_db_connection() as conn:
        book = conn.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
        if not book:
            abort(404)

    pdf_path = os.path.join(app.config["UPLOAD_FOLDER"], book["filename"])
    if not os.path.exists(pdf_path):
        abort(404)

    # Option 1: Serve directly with send_file
    from flask import send_file
    return send_file(pdf_path, mimetype="application/pdf")

    # Option 2 (Alternate): Return a link or an iframe
    # return f'<iframe src="/static/pdfs/{book["filename"]}" width="100%" height="800px"></iframe>'

if __name__ == "__main__":
    app.run(debug=True)
