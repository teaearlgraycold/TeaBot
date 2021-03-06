import praw
import sqlite3

class ModmaildB:
    """
    Module for collecting modmails into an SQLite database, and allowing for
    searching of that database
    """
    def __init__(self, r, subreddit):
        self.r = r
        self.subreddit = subreddit
        self.conn = sqlite3.connect('sqlite/' + subreddit.display_name + '.db')
        self.c = self.conn.cursor()

        self.initTable()

    def initTable(self):
        try:
            self.c.execute('SELECT * FROM modmail') # Check if table exists
        except sqlite3.OperationalError:
            print(self.subreddit.display_name + ': initializing database')
            self.r.send_message(self.subreddit, 'Modmail DataBase Status', 'Your modmail history is currently being archived as far back as is possible')
            
            self.c.execute('CREATE TABLE IF NOT EXISTS modmail (id text, user text, dest text, body text, time real, subject text)')
            self.loadBacklog()
            self.conn.commit()

    def addMail(self, modmail, commit=True):
        values = (modmail.id, modmail.author.name, modmail.dest, modmail.body, int(modmail.created_utc), modmail.subject)
        self.c.execute('INSERT INTO modmail VALUES (?,?,?,?,?,?)', values)
        
        if commit:
            self.conn.commit()

    def findMail(self, args):
        """
        Crummy search algorithm that allows for simple queries. Selectors for
        the to and from fields are allowed (as to:<username> and from:<username>).
        All other arguments are simply searched for within the body of the mail.
        """
        response = []

        for row in self.c.execute('SELECT * FROM modmail ORDER BY time DESC'):
            compliance = 0

            for arg in args:
                if arg[0:3] == 'to:' and row[2].lower() == arg[3:].lower():
                    compliance += 1
                elif arg[0:5] == 'from:' and row[1].lower() == arg[5:].lower():
                    compliance += 1
                elif arg[0:5] != 'from:' and arg[0:3] != 'to:' and arg.lower() in row[3].lower():
                    compliance += 1

            if compliance == len(args):
                if len(response) <= 25:
                    response.append(self.messageFromRow(row))
                else:
                    break

        return response

    def messageFromRow(self, row):
        """
        Creates a PRAW message object from an SQL response
        """
        jsondict = {'body': row[3], 
                    'created_utc': row[4],
                    'id': row[0],
                    'dest': row[2],
                    'subject': row[5],
                    'replies': None}

        if row[1][0] == '#':
            jsondict['author'] = self.r.get_subreddit(row[1][1:])
        else:
            jsondict['author'] = self.r.get_redditor(row[1])

        return praw.objects.Message(self.r, jsondict)

    def loadBacklog(self):
        count = 0

        for modmail in self.r.get_mod_mail(self.subreddit, params=None, limit=None):
            count += 1

            if (count % 100) == 0: 
                print(self.subreddit.display_name + ': ' + str(count) + ' modmails read')

            try:
                self.addMail(modmail, commit=False)

                for reply in modmail.replies:
                    count += 1

                    self.addMail(reply, commit=False)
            except Exception as e:
                pass

        self.conn.commit()

    def purgedB(self):
        try:
            self.c.execute('DROP TABLE modmail')
        except sqlite3.OperationalError:
            pass

        self.initTable()

    def close(self):
        self.conn.close()
