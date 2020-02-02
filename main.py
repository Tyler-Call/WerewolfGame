#! /usr/bin/python3
#bootstrap theme found at https://bootswatch.com/darkly/

from flask import Flask, render_template

app = Flask(__name__)

@app.route("/")
def home():
    return render_template("home.html")
    
if __name__ == "__main__":
    app.run(port=3088,debug=True)