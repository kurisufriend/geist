geist is a re-painting of Internet Relay Chat for the wayward youth.



dev notes:

goal: a web chat (websockets) that mirrors an IRC, with historical backlogs.

    how to do backlogs:
        run a bot in the channel being 'bridged'. save incoming IRC messages
        to a log. build the history out of that log or a reasonable slice of
        it, the last ~100 chats, whatever on page load. probably cache that,
        at some point, or don't if we don't need to.
        practicals:
            if we store IRC logs, we won't be able to replicate offhand geist
            messages as such. they'd be backlogged as messages from 
            geist (IRC). actually, silly me, they wouldn't be backlogged at
            all. problem solved: manually append our messages to the log at
            appropriate times. poss. issue: format. solutions: we could make
            a fake IRC message type for our logs, but generally use the IRC
            protocol format (e.g. GEISTPM instead of PRIVMSG), or we could
            make a custom logging format. the first one is better, KISS.

            the cache thing might be silly. the chat will be slow if we make
            it totally stateless like that. it's elegant, but impractical.
            we'll see.
    
    how to do mirroring:
        use that same bot to catch new relevant IRC messages (join/parts,
        privmsg, notice, topic, etc.) and wire it to geist state modification
        or action (update local user list, send everyone a message, do a 
        notice type thing, change the topic, respectively).
        practicals:
            this means we have a websockets server speaking some simple protocol
            to clients, a frontend that responds in kind, and an internal and
            essentially separate process that triggers on IRC message and
            asks the websockets server to do things, and likewise the websockets
            server should be able to ask the IRC server to do things when there's
            a message from there. neither knows about much of anything, the ws
            server can write irc.send("<name>: "+msg) and the irc handler can
            write wss.send({"type": "message", "data": {etc.}}) without knowing
            what it's actually doing.
            similarly, the IRC handler can directly manipulate the user list etc.
            we're going as simple as humanly possible here.
    
    how to serve this:
        this repo can just be a backend. the FE can be separate, served thru nginx
        or something. they don't actually need to communicate much at all, really.
        once it hits the backend, just have an init bundle give msgs, channel, topic,
        users. that's it! easy as pie. no need for a REST API just do everything over
        wss. or ws. whatever. 

    spec:
        websockets:
            client-sending:
                {"type": "hi", "data": {}}  <   client sends after conn, serb responds w/
                                                init package
                {"type": "gmsg", "data":    <   geist -> irc message
                    {"author": "cynic", "contents": "yo"}}
            server-sending:
                {"type": "imsg", "data":    <   irc->geist message
                    {"author": "cynic", "contents": "yo"}}
                {"type": "users", "data": {"who": ["emachine", echarlie]}}   < current irc user list
                {"type": "orientation", "data":{    < the init package
                    "backlog":  [...array of (i|g)msg objects...],
                    "channel":  "#vtluug",
                    "topic":    "hokietux worldwide",
                    "users":    [...list of all the users...]}}
    
    triggers:
        irc:
            onjoin: get NAMES, purge the local user list, and join everyone we find
                    TL Note: when i say 'user list', i do literally mean a [l, i , s, t].
                             we're just .append()ing here, folks. not that hard.
            user join: join them to the list, SEND ERRYONE TYPEUSERS TO WS
            user part: remove them from the list, SEND ERRYONE TYPEUSERS TO WS
            privmsg: SEND ERRYONE TYPEIMSG TO WS
        ws:
            onjoin: do jack shit for now lol don't wanna annoy the IRC ppl w infinite
                    remote joinparts from bots or shy people on mobile data or w/e
            user msg: send a reflective message to IRC
            literally anything else: do JACK FUCKING SHIT 
