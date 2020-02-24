#! /usr/bin/python3
#bootstrap theme found at https://bootswatch.com/darkly/

from flask import Flask, render_template, session, request, redirect, send_from_directory
from flask_socketio import SocketIO
from flask_socketio import send, emit, join_room, leave_room
import pymysql
import os, string, random, hashlib
import creds
import logging
from time import strftime
from logging.handlers import RotatingFileHandler
from DBUtils.PersistentDB import PersistentDB

app = Flask(__name__)
app.secret_key = creds.secretKey
socketio = SocketIO(app)
SALT = creds.salt


#con = pymysql.connect(creds.DBHost, creds.DBUser, creds.DBPass, creds.DBName,cursorclass=pymysql.cursors.DictCursor,autocommit=True)

def connect_db():
    '''Establishes DB connection'''
    return PersistentDB(
        creator = pymysql, # the rest keyword arguments belong to pymysql
        user = creds.DBUser, password = creds.DBPass, database = creds.DBName, 
        autocommit = True, charset = 'utf8mb4', 
        cursorclass = pymysql.cursors.DictCursor)

def get_db():
    '''Opens a new database connection per app.'''
    if not hasattr(app, 'db'):
        app.db = connect_db()
    return app.db.connection() 

def apply_role(role,playerList):
    while True: #will loop until a role is assigned
        randomPlayer = random.randrange(0,len(playerList))
        if playerList[randomPlayer]["role"] == "villager":
            playerList[randomPlayer]["role"] = role
            print("ASSIGNMENT: {} will be a: {}".format(playerList[randomPlayer]["username"],playerList[randomPlayer]["role"]))
            break

def assign_roles(game):
    #logic to assign roles based on rules
    # print("Players and roles before assignments:",game["gameLogic"])
    # print("PLAYERS NEEDED:",int(game["playersNeeded"]))
    if 6<= int(game["playersNeeded"]) <=9:
        apply_role("headWerewolf",game["gameLogic"])
        apply_role("seer",game["gameLogic"])
        apply_role("healer",game["gameLogic"])
    if 10<= int(game["playersNeeded"]) <=13:
        apply_role("headWerewolf",game["gameLogic"])
        apply_role("werewolf",game["gameLogic"])
        apply_role("seer",game["gameLogic"])
        apply_role("healer",game["gameLogic"])
    if 14<= int(game["playersNeeded"]) <=16:
        apply_role("headWerewolf",game["gameLogic"])
        apply_role("werewolf",game["gameLogic"])
        apply_role("werewolf",game["gameLogic"])
        apply_role("seer",game["gameLogic"])
        apply_role("healer",game["gameLogic"])
    #print("Players and roles AFTER assignments:",game["gameLogic"])
    return

def create_active_game(game):
    cur = get_db().cursor()
    #game: {"roomId":session["roomId"],"players":[session["username"]],"playersNeeded":request.form["playersNeeded"],"decisionTimer":decisionSeconds}
    #Gamelogic: {"username":player, "role":"villager", "isAlive":"1", "isReady":"0"}
    roomId = game["roomId"]
    decisionTimer = game["decisionTimer"]
    print("ADDING TO ActiveGames in DB!")
    for player in game["gameLogic"]:
        print("Creating entry for: {}".format(player["username"]))
        cur.execute("INSERT INTO ActiveGames (Username, RoomId, Role, DecisionTimer) VALUES (%s, %s, %s, %s)",(player["username"], roomId, player["role"], decisionTimer))
    cur.close()
    return

GAMES = [] #holds all active games with "roomId" and "players" - list of players

def roomGenerator(size=4, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))

"""Handles the connection log after each request comes in (see last section of code)"""
@app.after_request
def after_request(response):
    timestamp = strftime('[%Y-%b-%d %H:%M]')
    logger.error('%s %s %s %s %s %s', timestamp, request.remote_addr, request.method, request.scheme, request.full_path, response.status)
    return response

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico')

@app.route("/")
def home():
    return render_template("home.html")

@app.route("/login")
def login():
    return render_template("login.html")

@app.route("/verify",methods=['POST'])
def verify():
    hashedPass = hashlib.md5((request.form["password"] + SALT).encode())
    print("HASHED PASS:",hashedPass.hexdigest())
    cur = get_db().cursor()
    cur.execute("SELECT Password FROM User WHERE Username = %s",(request.form['username']))
    result = cur.fetchall()
    cur.close()
    if len(result) == 0:
        return render_template("login.html",error="badUsername")
    elif hashedPass.hexdigest() != result[0]["Password"]:
        return render_template("login.html",error="badPassword")
    else:
        
        cur = get_db().cursor()
        cur.execute("UPDATE User SET LoggedIn = 1 WHERE Username = %s",(request.form['username']))
        cur.execute("SELECT UserId FROM User WHERE Username = %s",(request.form['username']))
        result = cur.fetchone()
        cur.close()
        session["userId"] = result["UserId"]
        session["username"] = request.form['username']
        session['loggedIn'] = 1
        return redirect("/game")

@app.route("/guestlogin")
def guestlogin():
    cur = get_db().cursor()
    cur.execute("SELECT MAX(UserId) AS HighestID FROM User")
    highestId = cur.fetchone()
    guestId = int(highestId["HighestID"]) + 1
    cur.execute("INSERT INTO User (Username, Password, IsGuest, LoggedIn) VALUES (%s, %s, '0', '1')",('Guest#{}'.format(guestId),random.getrandbits(128)))
    cur.execute("SELECT UserId FROM User WHERE Username =%s",('Guest#{}'.format(guestId)))
    UserId = cur.fetchone()
    cur.close()
    session["userId"] = UserId["UserId"]
    session["username"] = 'Guest#{}'.format(guestId)
    session['loggedIn'] = 1
    # print("SESSION VARS:",session)
    return redirect("game")

@app.route("/stats")
def stats():
    try:
        if session["loggedIn"]:
            cur = get_db().cursor()
            cur.execute("SELECT * FROM Stats WHERE UserId = %s",(session['userId']))
            result = cur.fetchall()
            cur.close()
            error = None
            stats = None
            if len(result) == 0:
                error = "isGuest"
            else:
                stats = result[0]
            if error == "isGuest":
                return render_template("game.html",error=error)
            # return render_template("stats.html",gamesPlayed=stats["GamesPlayed"],gamesWon=stats["gamesWon"],peopleEaten=stats["peopleEaten"])
            return render_template("stats.html",stats=stats)
    except:
        return redirect("/")

@app.route("/signout")
def signout():
    cur = get_db().cursor()
    if "Guest#" in session["username"]:
        print(f"{session['username']} signed out. Deleting from DB.")
        cur.execute("DELETE FROM User WHERE UserId = %s",(session['userId']))
    cur.execute("UPDATE User SET LoggedIn = 0 WHERE Username = %s",(session['username']))
    cur.close()
    session.clear()
    return redirect("/")

@app.route("/signup")
def signup():
    try:
        if session["loggedIn"]:
            return redirect("/")
    except:
        return render_template("signup.html")

@app.route("/createAccount",methods=['POST'])
def createAccount():
    try:
        if session["loggedIn"]:
            return redirect("/")
    except:
        # print(request.form)
        if request.form["password"] != request.form["confirmPassword"]:
            return render_template("signup.html",error="badPassword")
        cur = get_db().cursor()
        cur.execute("SELECT * FROM User WHERE Username = %s",(request.form['username']))
        result = cur.fetchall()
        cur.close()
        if len(result) != 0: #the username already exists in the db
            return render_template("signup.html",error="badUsername")
        else:
            hashedPass = hashlib.md5((request.form["password"] + SALT).encode()).hexdigest()
            cur = get_db().cursor()
            try: #with email
                cur.execute("INSERT INTO User (Username, Password, Email, IsGuest, LoggedIn) VALUES (%s, %s, %s, '0', '1')",(request.form['username'],hashedPass,request.form['email']))
            except: #without email
                cur.execute("INSERT INTO User (Username, Password, IsGuest, LoggedIn) VALUES (%s, %s, '0', '1')",(request.form['username'],hashedPass))
            cur.execute("SELECT UserId FROM User WHERE Username = %s",(request.form['username']))
            result = cur.fetchall()
            cur.execute("INSERT INTO Stats (UserId) VALUES (%s)",(result[0]["UserId"]))
            session["userId"] = result[0]["UserId"]
            session["username"] = request.form["username"]
            session['loggedIn'] = 1
            cur.close()
            return redirect("game")

@app.route("/game")
def game():
    try:
        if session["loggedIn"]:
            return render_template("game.html")
    except:
        return redirect("/")

@app.route("/create")
def create():
    try:
        if session["loggedIn"]:
            return render_template("create.html")
    except:
        return redirect("/login")

@app.route("/createGame",methods=['POST'])
def createGame():
    try:
        if session["loggedIn"]:
            try:
                if session["roomId"]:
                    print("The user {} tried to make a new room, but they are already in room {}!".format(session["username"],session["roomId"]))
                    print("Removing old roomId to create a new room.")
                    session.pop('roomId', None)
            except:
                pass #the user is not already in a room
            decisionSeconds = int(request.form["decisionTimer"])*60
            newRoomId = roomGenerator()
            session["roomId"] = newRoomId
            # print("*****************\nROOM ID GENERATED: {}".format(session["roomId"]))
            # print("Variables from form:\nDecision in seconds:",decisionSeconds,"\nPlayers needed:", request.form["playersNeeded"])
            # print("*****************")
            playersInt = int(request.form["playersNeeded"])
            cur = get_db().cursor()
            cur.execute("INSERT INTO Lobby (RoomId, PlayersNeeded, DecisionTimer) VALUES (%s, %s, %s)",(newRoomId,int(request.form["playersNeeded"]),int(decisionSeconds)))
            cur.close()
            newGame = {"roomId":session["roomId"],"players":[session["username"]],"playersNeeded":request.form["playersNeeded"],"decisionTimer":decisionSeconds}
            GAMES.append(newGame)
            print("Making new game:",newGame)
            print("All active games:",GAMES)
            return redirect("lobby")
    except Exception as e:
        print("**ERROR in create game:",e)
        return redirect("/")

@app.route("/joinGame", methods=['POST'])
def joinGame():
    try:
        try:
            if session["roomId"]:
                print("The user {} tried to join room {}, but they are already in room {}!".format(session["username"],request.form["roomId"],session["roomId"]))
                print("Removing old roomId to join a new room.")
                session.pop('roomId', None)
        except:
            pass #the user is not already in a room
        if session["loggedIn"]:
            for game in GAMES:
                if request.form["roomId"] == game["roomId"]:
                    session["roomId"] = request.form["roomId"]
                    game["players"].append(session["username"])
                    cur = get_db().cursor()
                    cur.execute("UPDATE Lobby SET CurrentPlayers = CurrentPlayers + 1 WHERE RoomId = %s",(session["roomId"]))
                    cur.close()
                    print("The user {} is joining the lobby: {}".format(session["username"],session["roomId"]))
                    roomId = session["roomId"]
                    return redirect("lobby")
            print("The user {} is entered invalid roomId: {}".format(session["username"],request.form["roomId"]))
            return redirect("/game")          
    except Exception as e:
        print("**ERROR in join game:",e)
        return redirect("/")

@app.route("/lobby")
def lobby():
    try:
        if session["loggedIn"] and session["roomId"]:
            playersNeeded = 0
            currentPlayers = 0
            gameDict = None
            for game in GAMES:
                if game["roomId"] == session["roomId"]:
                    currentPlayers=len(game["players"])
                    playersNeeded=game["playersNeeded"]
                    gameDict = game
            if int(currentPlayers) == int(playersNeeded):#TODO: add all players from players list in GAMES to ActiveGames in the DB
                print(f"Player count reached for {session['roomId']}... REDIRECTING!")
                for game in GAMES:
                    if game["roomId"] == session["roomId"]:
                        game["gameLogic"] = []
                        for player in game["players"]:
                            game["gameLogic"].append({"username":player, "role":"villager", "isAlive":"1", "isReady":"0"})
                        assign_roles(game) #assigns roles to players
                        create_active_game(game) #adds players to ActiveGames table in DB
                socketio.emit('start game', room=session["roomId"])
                return redirect("pregame")
            else:
                return render_template("lobby.html",roomId=session["roomId"],currentPlayers=currentPlayers,playersNeeded=playersNeeded,playerNames=gameDict["players"])
    except Exception as e:
        print("**ERROR in lobby route:",e)
        return redirect("/")

@app.route("/leaveLobby")
def leaveLobby():
    try:
        if session["loggedIn"] and session["roomId"]:
            for game in GAMES:
                if game["roomId"] == session["roomId"]:
                    userList =  game["players"]
                    for user in game["players"]:
                        if user == session["username"]:
                            game["players"].remove(user)
                            print("The user {} left the lobby: {}".format(session["username"],session["roomId"]))
                            cur = get_db().cursor()
                            cur.execute("UPDATE Lobby SET CurrentPlayers = CurrentPlayers - 1 WHERE RoomId = %s",(session["roomId"]))
                            cur.close()
                            socketio.emit('reload users', userList,room=session["roomId"]) #tells view for all players in the lobby to refresh
                    # print("Players left in the lobby:",len(game["players"]))
                    if len(game["players"]) == 0:
                        print("Nobody is in the lobby: {}. Deleting the lobby.".format(session["roomId"]))
                        cur = get_db().cursor()
                        cur.execute("DELETE FROM Lobby WHERE RoomId = %s",(session["roomId"]))
                        cur.close()
                        GAMES.remove(game)
                        print("Remaining lobbies:",GAMES)
            session.pop('roomId', None)
            return redirect("/game")
    except Exception as e:
        print("**ERROR in leaveLobby route:",e)
        return redirect("/")

@app.route("/pregame")
def pregame():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    for game in GAMES:
        if game["roomId"] == session["roomId"]:
            for player in game["gameLogic"]:
                if player["username"] == session["username"]:
                    session["role"] = player["role"]
    #get role description text based on session variable and pass to pregame
    return render_template("gameViews/pregame.html")

@app.route("/intro")
def intro():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    return render_template("gameViews/intro.html")

@app.route("/daytime")
def daytime():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    return render_template("gameViews/daytime.html")

@app.route("/nighttime")
def nighttime():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    return render_template("gameViews/nighttime.html")

@app.route("/vote")
def vote():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    return render_template("gameViews/vote.html")

@app.route("/results")
def results():
    # try:
    #     if session["loggedIn"]:
    #         return render_template("create.html")
    # except:
    #     return redirect("/login")
    return render_template("gameViews/results.html")

@app.route("/sessionDestroy")
def sessionDestroy():
	session.clear()
	return redirect("/")

@app.route("/sessionView")
def sessionView():
    print("*************")
    print(session)
    print("*************")
    return redirect("/")

""" SOCKET ROUTES BELOW """

@socketio.on('lobby entered')
def lobbyNotify(roomId):
    print(f"\nA player joined the room {roomId}\n")
    join_room(roomId)
    userList = None
    for game in GAMES:
        if roomId == game["roomId"]:
            userList=game["players"]
    # print(f"Sending: reload users in lobby to the lobby...\n This is the user list:{userList}")
    emit('reload users', userList, room=roomId)

# @socketio.on('refresh lobby list')
# def refreshLobby(roomId):
#     print("The room is be refreshed is:",roomId)
#     userList = None
#     for game in GAMES:
#         if roomId == game["roomId"]:
#             userList=game["players"]
#     print(f"A user left the lobby {roomId}.\n This is the new user list:{userList}")
#     emit('reload users', userList, room=roomId)




@app.errorhandler(404)
def page_not_found(error):
   return render_template('404.html'), 404

if __name__ == "__main__":
    handler = RotatingFileHandler('../backups/werewolfConnection.log', maxBytes=100000, backupCount=3)
    logger = logging.getLogger('tdm')
    logger.setLevel(logging.ERROR)
    logger.addHandler(handler)
    socketio.run(app, host='0.0.0.0',port=3088, log_output=True, debug=True)
