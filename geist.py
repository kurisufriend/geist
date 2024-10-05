import websockets, json, threading
from random import choice
from ircked.bot import irc_bot
from ircked.message import *

class geist():
    def __init__(self, config_path = "./config.json"):
        self.irc_users = []
        self.geist_users = {}

        with open(config_path, "r") as f:
            self.config = json.loads(f.read())

        self.bot = irc_bot(self.config["irc_nick"], 
            "geist", 
            choice(["blinky", "pinky", "inky", "clyde"]))
        
    def run(self):
        self.bot.connect_register(self.config["irc_server"], self.config["irc_port"])
        def irc_handler(msg, ctx):
            #print("<<", str(msg))
            handler = getattr(self, "irc_"+msg.command.lower(), None)
            try:
                handler(msg, ctx)
            except TypeError:
                print("unhandled IRC message:", str(msg))
        threading.Thread(target=self.bot.run, args=(irc_handler,)).start()
    
    def handle_irc_msg(self, author, body):
        pass

    # woo woo woo woo stayin' alive
    def irc_ping(self, msg, ctx):
        self.bot.sendraw(message.manual("", "PONG", msg.parameters))

    # 001 is basically ON_READY. join up w the squad.
    def irc_001(self, msg, ctx):
        self.bot.sendraw(message.manual("", "JOIN", [self.config["irc_channel"]]))

    def irc_privmsg(self, msg, ctx):
        # we're being queried by aliens. assume a suitable disguise.
        if "\x01VERSION\x01" in msg.parameters:
            self.bot.sendraw(message.manual(":"+msg.parameters[0], "PRIVMSG", [msg.prefix[1:].split("!")[0], ":\x01dorfl/geist\x01"]))
            return
        
        # we got a message!!!!
        pm = privmsg.parse(msg)
        if pm.bod == ".hello":
            self.bot.sendraw(privmsg.build(ctx.nick, pm.to, "hello, world!").msg)

