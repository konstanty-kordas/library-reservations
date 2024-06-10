from db import DB
from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
import random


def test_1(db: DB):
    MAX_WORKERS = 16
    book_id = db.get_book()[0]
    NUM_ITERS = 10000
    start = perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for _ in range(NUM_ITERS):
            executor.submit(db.borrow_book, "tester", book_id.hex, False)
    finish = perf_counter()
    print(f"It took {finish-start} second(s) to finish.")
    db.cleanup()


def test_2(db: DB):
    MAX_WORKERS = 16
    NUM_ITERS = 10000

    def client_request():
        book_id = random.choice(db.get_books())[0]
        db.borrow_book(
            random.choice([f"tester_{i}" for i in range(1, MAX_WORKERS + 1)]),
            str(book_id),
            False,
        )

    start = perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for _ in range(NUM_ITERS):
            executor.submit(client_request)

    finish = perf_counter()
    print(f"It took {finish-start} second(s) to finish.")
    db.cleanup()


def test_3(db: DB):
    MAX_WORKERS = 2

    def borrow_all(tester_id):
        all_books = db.get_books()
        for book in all_books:
            db.borrow_book(f"tester_{tester_id}", str(book[0]), False)

    start = perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for _ in range(MAX_WORKERS):
            for tester_id in range(1, MAX_WORKERS + 1):
                executor.submit(borrow_all, tester_id)

    finish = perf_counter()
    print(f"It took {finish-start} second(s) to occupy all seats/reservations.")
    for tester_id in range(1, MAX_WORKERS + 1):
        borrowed = db.get_books_user(f"tester_{tester_id}")
        print(f"tester_{tester_id} borrowed {borrowed} books")
    db.cleanup()

def test_4(db: DB):
    MAX_WORKERS = 10

    def borrow_all(tester_id):
        all_books = db.get_books()
        for book in all_books:
            db.borrow_book(f"tester_{tester_id}", str(book[0]), False)

    start = perf_counter()

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for _ in range(MAX_WORKERS):
            for tester_id in range(1, MAX_WORKERS + 1):
                executor.submit(borrow_all, tester_id)

    finish = perf_counter()
    print(f"It took {finish-start} second(s) to occupy all seats/reservations.")
    for tester_id in range(1, MAX_WORKERS + 1):
        borrowed = db.get_books_user(f"tester_{tester_id}")
        print(f"tester_{tester_id} borrowed {borrowed} books")
    db.cleanup()

def tests(db: DB, user: str):
    while True:
        print("STRESS TESTS:")
        print("1: The client makes the same request very quickly (10000 times).")
        print(
            "2: Two or more clients make the possible requests randomly (10000 times)."
        )
        print("3: Immediate occupancy of all seats/reservations by 2 clients.")
        print("0: Back")
        test = input("Which test do you wish to run?\n")
        if test == "1":
            test_1(db)
        elif test == "2":
            test_2(db)
        elif test == "3":
            test_3(db)
        elif test == "4":
            test_4(db)
        elif test == "0":
            break
        else:
            print("Pick one of the available options")


if __name__ == "__main__":
    # tests()
    db = DB()
    seed = input("Do you want to seed the database? t/F\n")
    if seed == "t":
        x = input("How many rows do you wish to insert? [20]\n")
        if x.isnumeric():
            print(f"Inserting {x} rows...")
            db.seed(int(x))
        else:
            print("Inserting 20 rows...")
            db.seed()

    while True:
        user = input("Log in: ")
        if user == "":
            print("Enter your username")
        else:
            break

    print(f"Welcome, {user}")
    print("What do you want to do?")
    while True:
        menu = input(
            "1: Show all books, 2: Show your borrowed books, 3: Borrow a book, 4: Return a book, 5: Extend the time on a book, 6: Run stress tests, 0: Exit\n"
        )
        if menu == "1":
            db.display_books()
        elif menu == "2":
            db.display_borrowed_books_by_user(user)
        elif menu == "3":
            borrow_book_id = input(
                "Please insert book id which you want to borrow:\n"
            ).strip()
            db.borrow_book(user, borrow_book_id)
        elif menu == "4":
            reservation_id = input(
                "Please insert id of the reservation you want to end:\n"
            ).strip()
            db.return_book(reservation_id, user)
        elif menu == "5":
            reservation_id = input(
                "Please insert id of the reservation you want to extend:\n"
            ).strip()
            db.renew_book(reservation_id, user)
        elif menu == "6":
            tests(db, user)
        elif menu == "0":
            print("Exiting...")
            break
        else:
            print("Sorry, this isn't an available option.")
