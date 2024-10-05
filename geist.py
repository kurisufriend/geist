import websockets, json, threading
from random import choice
from ircked.bot import irc_bot
from ircked.message import *

class geist():
    def __init__(self, config_path = "./config.json"):
        self.irc_users = set()
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
    
    # reply to NAMES, params are a list of all the names
    def irc_353(self, msg, ctx):
        # get rid of the leading colon & meta stuff
        names = self._helper_trim_param_errata(msg.parameters)
        names[0] = names[0][1:]
        # filter out ops of all sorts and voices
        #  some ircds probably have more goofy role symbols but i frankly don't care
        for i in range(len(names)):
            for r in ["@", "+", "%", "&", "~"]:
                names[i] = names[i].replace(r, "")
        # add all these guys to our set
        for n in names:
            self.irc_users.add(n)

    def irc_join(self, msg, ctx):
        # the nick that joined
        nick = msg.prefix[1:].split("!")[0]
        # us joining the desired channel. take names!
        if nick == self.config["irc_nick"]:
            self.irc_users = set()
            self.bot.socket.send(f"NAMES {msg.parameters[0][1:]}\r\n".encode("utf-8"))
            return
        # otherwise, add the newbie
        self.irc_users.add(nick)
        
    def irc_part(self, msg, ctx):
        # the nick that left
        nick = msg.prefix[1:].split("!")[0]
        # bye bye
        self.irc_users.remove(nick)

    def irc_privmsg(self, msg, ctx):
        # we're being queried by aliens. assume a suitable disguise.
        if "\x01VERSION\x01" in msg.parameters:
            self.bot.sendraw(message.manual(":"+msg.parameters[0], "PRIVMSG", [msg.prefix[1:].split("!")[0], ":\x01dorfl/geist\x01"]))
            return
        
        # we got a message!!!!
        pm = privmsg.parse(msg)
        if pm.bod == ".hello":
            self.bot.sendraw(privmsg.build(ctx.nick, pm.to, "hello, world!").msg)

    # sometimes messages have random bullshit we don't want before the first colon-param
    def _helper_trim_param_errata(self, params):
        res = []
        flip = False
        for i in params:
            if i.startswith(":"): flip = True
            if flip: res.append(i)
        return res