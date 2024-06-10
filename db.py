import uuid
from datetime import datetime, timedelta

import pandas as pd
from cassandra.cluster import Cluster, BatchStatement
from prettytable import PrettyTable


class DB:
    def __init__(self) -> None:
        self.cluster = Cluster(
            [("127.0.0.1", 9042), ("127.0.0.2", 9043), ("127.0.0.3", 9044)]
        )
        query_keyspace = """CREATE KEYSPACE IF NOT EXISTS library_reservation 
            WITH REPLICATION = { 
                'class' : 'SimpleStrategy', 'replication_factor' : 1 
            };"""
        self.session = self.cluster.connect()
        self.session.execute(query_keyspace)
        print("CREATED KEYSPACE")
        self.session = self.cluster.connect("library_reservation")

        query_table_books = """CREATE TABLE IF NOT EXISTS Books (
            book_id UUID PRIMARY KEY,
            title text, 
            author text,
        );"""
        query_table_reservations = """CREATE TABLE IF NOT EXISTS Reservations (
            reservation_id UUID,
            book_id UUID,
            user TEXT,
            due_date TIMESTAMP,
            PRIMARY KEY (user, reservation_id)
        );"""

        query_table_borrowed = """CREATE TABLE IF NOT EXISTS Borrowed (
            book_id UUID PRIMARY KEY
        );"""
        query_table_resource_locks = """CREATE TABLE IF NOT EXISTS resource_locks (
            resource_id UUID PRIMARY KEY,
            locked_by text,
            lock_time TIMESTAMP
        );"""

        self.session.execute(query_table_books)
        self.session.execute(query_table_reservations)
        self.session.execute(query_table_borrowed)
        self.session.execute(query_table_resource_locks)

        print("Initialisation Complete")

    def seed(self, n: int = 20) -> None:
        self.session.execute("TRUNCATE Books")
        self.session.execute("TRUNCATE Reservations")
        self.session.execute("TRUNCATE Borrowed")
        self.session.execute("TRUNCATE resource_locks")

        books = pd.read_csv("books.csv")
        better_books = pd.DataFrame(
            books, columns=["book_id", "authors", "original_title"]
        )
        better_books["author"] = better_books["authors"].str.split(",").str[0]
        better_books["title"] = better_books["original_title"]
        better_books.drop(columns=["authors", "original_title"], inplace=True)
        better_books.dropna(inplace=True)
        insert_book = self.session.prepare(
            "INSERT INTO books (book_id,title, author) VALUES (?,?,?)"
        )
        seeds = better_books.sample(n)
        for index, row in seeds.iterrows():
            r = row.to_dict()
            bid = uuid.uuid4()
            title = r["title"]
            author = r["author"]
            self.session.execute(insert_book, (bid, title, author))

        print("SEEDED")

    def get_book(self):
        query = """SELECT * FROM books"""
        res = self.session.execute(query).one()
        return res

    def get_books(self):
        query = """SELECT * FROM books"""
        res = self.session.execute(query).all()
        return res

    def get_books_user(self, user):
        res = self.session.execute(
            f"""SELECT * from Reservations where user = '{user}';"""
        )
        if res.one() is None:
            return 0
        return len(res.all())

    def cleanup(self):
        self.session.execute("TRUNCATE Reservations")
        self.session.execute("TRUNCATE Borrowed")

    def display_books(self) -> None:
        query = """SELECT * FROM books"""
        res = self.session.execute(query)
        t = PrettyTable(["ID", "Title", "Author"])
        for row in res:
            t.add_row([i for i in row])
        print(t)

    def acquire_lock(self, book_id, user_id):
        prepared_lock_query = self.session.prepare("""
            INSERT INTO resource_locks (resource_id, locked_by, lock_time)
            VALUES (?,?,?)
            IF NOT EXISTS;
        """)
        now = datetime.now()
        result = self.session.execute(
            prepared_lock_query, (uuid.UUID(book_id), user_id, now)
        )
        return result.was_applied

    def borrow_book(self, user: str, book_id: str, log=True):
        try:
            uuid.UUID(book_id)
        except ValueError:
            print("Please provide correct book id")
            return

        book_exists_query = self.session.prepare(
            "SELECT * from Books WHERE book_id = ?"
        )
        ret = self.session.execute(book_exists_query, [uuid.UUID(book_id)]).one()
        if ret is None:
            if log:
                print("Book doesn't exist")
            return

        borrowed_query = self.session.prepare(
            "SELECT * from Borrowed WHERE book_id = ?"
        )
        ret = self.session.execute(borrowed_query, [uuid.UUID(book_id)]).one()
        if ret is not None:
            if log:
                print("Book is not available")
            return

        lock = self.acquire_lock(book_id, user)
        if not lock:
            if log:
                print("Book is not available")
            return
        check_query = self.session.prepare(
            "SELECT locked_by FROM resource_locks WHERE resource_id = ?"
        )
        user_locked = self.session.execute(check_query, [uuid.UUID(book_id)]).one()[0]
        if user != user_locked:
            if log:
                print("Book is not available")
            return
        batch = BatchStatement()
        borrow_query = self.session.prepare(
            "INSERT INTO Reservations (reservation_id ,book_id, user, due_date) VALUES (?,?,?,?)"
        )
        batch.add(
            borrow_query,
            (
                uuid.uuid4(),
                uuid.UUID(book_id),
                user,
                datetime.now() + timedelta(days=30),
            ),
        )
        borrow_query_block = self.session.prepare(
            "INSERT INTO Borrowed (book_id) VALUES (?)"
        )
        batch.add(borrow_query_block, [uuid.UUID(book_id)])

        lock_query = self.session.prepare("""
            DELETE FROM resource_locks
            WHERE resource_id = ?;
            """)
        batch.add(lock_query, [uuid.UUID(book_id)])
        self.session.execute(batch)

    def get_reservation_details(self, user: str, reservation_id: str):
        try:
            uuid.UUID(reservation_id)
        except ValueError:
            print("Please provide correct reservation id")
            return

        details_query = self.session.prepare(
            "SELECT * FROM Reservations WHERE user=? and reservation_id = ?"
        )
        reservation_details = self.session.execute(
            details_query, (user, uuid.UUID(reservation_id))
        ).one()
        return reservation_details

    def renew_book(self, reservation_id: str, user: str):
        try:
            uuid.UUID(reservation_id)
        except ValueError:
            print("Please provide correct reservation id")
            return

        update_query = self.session.prepare(
            "UPDATE Reservations SET due_date=? WHERE user=? and reservation_id = ?;"
        )
        reservation_details = self.get_reservation_details(user, reservation_id)
        if reservation_details is None:
            print("Reservation does not exist")
        old_timestamp = reservation_details[3]
        new_timestamp = old_timestamp + timedelta(days=30)
        self.session.execute(
            update_query, (new_timestamp, user, uuid.UUID(reservation_id))
        )

    def display_borrowed_books_by_user(self, user: str):
        res = self.session.execute(
            f"""SELECT * from Reservations where user = '{user}';"""
        )
        if res.one() is None:
            print("You have no books borrowed.")
            return

        t = PrettyTable(["Reservation ID", "Title", "Author", "Due Date"])
        for row in res:
            book_id = row[2]
            due_date = f"{row[3].day}/{row[3].month}/{row[3].year}"
            details_query = self.session.prepare(
                "SELECT * FROM books where book_id = ?"
            )
            book_details = self.session.execute(details_query, [book_id]).one()
            t.add_row((row[1], book_details[2], book_details[1], due_date))
        print(t)

    def return_book(self, reservation_id: str, user: str):
        try:
            uuid.UUID(reservation_id)
        except ValueError:
            print("Please provide correct reservation id")
            return

        reservation_details = self.get_reservation_details(user, reservation_id)
        if reservation_details is None:
            print("Reservation does not exist")
            return

        batch = BatchStatement()
        borrow_query = self.session.prepare(
            "DELETE FROM Reservations WHERE user=? AND reservation_id = ?;"
        )
        batch.add(borrow_query, [user, uuid.UUID(reservation_id)])
        borrow_query_block = self.session.prepare(
            "DELETE FROM Borrowed WHERE book_id=? ;"
        )
        batch.add(borrow_query_block, [reservation_details[2]])
        self.session.execute(batch)
        print("Returned book", reservation_details[2])
