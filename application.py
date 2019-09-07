import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.route("/")
@login_required
def index():

    """Show portfolio of stocks"""
    # SELECT NEEDED INFORMATION FOR SQL TABLE
    user = db.execute("SELECT username FROM users WHERE id = :id", id = session['user_id'])
    username = user[0]["username"]
    rows = db.execute("SELECT stock, SUM(shares) AS shares FROM portfolio WHERE username = :username GROUP BY stock", username = username)
    # SELECT CASH INFO
    result = db.execute("SELECT cash FROM users WHERE id = :id", id = session['user_id'])
    # DECLARE VARIABLES FOR CALCULATIONS WITHIN FOR LOOP
    balance = float(result[0]['cash'])
    total_holdings = balance
    val = []

    for row in rows:
        stockie = row["stock"]
        shares = int(row["shares"])
        val = lookup(row["stock"])
        # CREATE NEW VARIABLES WITH UP TO DATE INFORMATION
        # ON THE CURRENT PRICE OF THE SHARE HOLDINGS
        row["priced"] = usd(float(val.get("price")))
        row["cost"] = usd(float(val.get("price") * shares))
        # UPDATE TOTAL HOLDINGS
        total_holdings += float(val.get("price") * shares)

    # RETURN TABLE WITH TOTAL HOLDINGS INFORMATION
    return render_template("index.html", rows = rows, balance = usd(balance), total_holdings = usd(total_holdings))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        # GET THE STOCK SYMBOL FROM THE FORM
        stock = request.form.get("symbol")
        # SET VARIABLE EQUAL TO NUMBER OF SHARES TO BUY
        test = request.form.get("shares")
        # CREATE DICT TO STORE PRICE OF THOSE SHARES
        priced=[]
        # LOOKUP STOCK INFO
        priced = lookup(stock)
        #CHECK PROPER USAGE
        if not stock or not priced:
            return apology("Please submit a valid symbol.", 400)
        elif not test.isdigit():
            return apology("Please submit a valid ammount of shares.", 400)
        shares = float(request.form.get("shares"))
        if shares < 1:
            return apology("Please submit a valid ammount of shares", 400)
        # TOTAL COST TO BUY THOSE SHARES OF THAT STOCK
        cost = float(priced["price"])
        purchase = float(cost * shares)
        # HOW MUCH CASH DO THEY HAVE
        total = db.execute("SELECT cash FROM users WHERE id = :id", id = session['user_id'])
        # WHICH USER IS IT
        username = db.execute("SELECT username FROM users WHERE id = :id", id = session['user_id'])
        # VARIABLES TO STORE THAT INFORMATION
        # NEEDED TO UPDATE THE SQL TABLE
        user = username[0]["username"]
        cash = total[0]["cash"]

        # IF THEY HAVE ENOUGH MONEY UPDATE THE TABLE OTHERWISE RETURN APOLOGY
        if purchase < cash:
            db.execute("INSERT INTO portfolio (stock, shares, price, username) VALUES(:stock, :shares, :price, :username)",
                stock = stock, shares = shares, price = usd(cost), username = user)
            db.execute("UPDATE users SET cash = (cash - :purchase) WHERE id = :id", id = session['user_id'], purchase = purchase)
        elif purchase > cash:
            return apology("You do not have the money to purchase these stocks", 400)

        # HOMEPAGE THAT SHOWS UPDATES STOCKS
        # Redirect user to home page
        return redirect("/")
    else:
        return render_template("buy.html")



@app.route("/check", methods=["GET"])
def check():
    """Return true if username available, else false, in JSON format"""
    username = request.args.get("username")
    use = db.execute("SELECT username FROM users WHERE username = :username", username = username)

    if username and use:
        return jsonify(False)
    else:
        return jsonify(True)


@app.route("/password", methods=["GET"])
def password():
    """Return true if username available, else false, in JSON format"""

    password = request.args.get("password")
    numbers = sum(pas.isdigit() for pas in password)

    if numbers > 1:
        return jsonify(True)
    else:
        return jsonify(False)

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    user = db.execute("SELECT username FROM users WHERE id = :id", id = session['user_id'])
    username = user[0]['username']
    history = db.execute("SELECT stock, shares, price, date FROM portfolio WHERE username = :username", username = username)

    for his in history:
        stock = his["stock"]
        shares = his["shares"]
        price = his["price"]
        date = his["date"]
    return render_template('historied.html', history = history)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote"""

    if request.method == "POST":
        # CREATE DICT ITEM
        val = []
        # GRAB SYMBOL FROM FORM
        symb = request.form.get("symbol")
        # LOOKUP SYMBOL INFO (HELPERS.PY)
        val = lookup(symb)
        # IF IT RETURNS A NONETYPE
        if not symb or not val:
            return apology("Please submit a valid symbol.")
        # RETURN A FORM WITH THE PRICE PER SHARE OF THAT STOCKS
        return render_template("quoted.html", symbol = val["name"], value = usd(val["price"]))

    else:
        return render_template("quote.html")



@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    # AFTER POSTING DO THIS
    if request.method == "POST":
        # CHECK FOR PROPER USAGE
        if not request.form.get("username"):
            return apology("Please submit a username", 400)
        elif not request.form.get("password") or not request.form.get("confirmation"):
            return apology("Please type in a password", 400)
        if not request.form.get("password") == request.form.get("confirmation"):
            return apology("Your passwords don't match", 400)

        # CREATE A HASH TO PROTECT PASSWORD
        hash_pass = generate_password_hash(request.form.get("password"))
        # INSERT NEW ROW WITH USER INFORMATION
        result = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)", username=request.form.get("username"), hash=hash_pass)

        # CHECK FOR UNIQUE USERNAME
        if not result:
            return apology("Error: non-unique username")
        session["user_id"] = result

        # RETURN THE LOGIN WINDOW ONCE REGISTERED
        return render_template("login.html")

    # OTHERWISE RETURN REGISTRATION WINDOW
    else:
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    user = db.execute("SELECT username FROM users WHERE id = :id", id = session['user_id'])
    username = user[0]["username"]
    symbol = db.execute("SELECT stock, shares FROM portfolio WHERE username = :username GROUP BY stock", username = username)

    for sym in symbol:
        stock = sym["stock"]

    # USER SUBMIT A SALE
    if request.method == "POST":

        # GET WHICH STOCK SYMBOL TO UPDATE AND SHARES TO SELL
        symbolie = request.form.get("symbol")
        test = (request.form.get("shares"))
        stock = symbol[0]["stock"]


        # GET THE NUMBER OF SHARES AVAILABLE TO SELL
        share = db.execute("SELECT SUM(shares) AS shares FROM portfolio WHERE username = :username AND stock = :symbolie GROUP BY stock", username = username, symbolie = symbolie)
        shares = share[0]["shares"]

        # CHECK PROPER USAGE
        if not test.isdigit():
            return apology("That is not a valid number of shares or you do not own that many shares", 400)
        sharys = int(test)
        if not symbolie:
            return apology("That is not a valid stock. Please try again.", 400)
        elif not sharys or sharys < 0 or shares < sharys:
            return apology("That is not a valid number of shares or you do not own that many shares", 400)


        # UPDATE USERS CASH FOLLOWING SALE
        quote = []
        quote = lookup(symbolie)
        price = float(quote["price"])
        sale = float(price * sharys)

        db.execute("UPDATE users SET cash = (cash + :sale) WHERE id = :id", id = session['user_id'], sale = usd(sale))


        # RECORD AS A NEGATIVE SALE
        neg = (-sharys)
        db.execute("INSERT INTO portfolio (stock, shares, price, username) VALUES (:stock, :shares, :price, :username)", username = username, shares = neg, price = price, stock = symbolie)


        # Redirect user to home page
        return redirect("/")

    # RETURN SELL.HTML
    else:
        return render_template("sell.html", symbol = symbol)




def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
