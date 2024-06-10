# Report
## Project description
This is the project for the Big Data and Distributed Systems subject for AI 6 semester bachelor studies at PUT.
It models a library, which allows to borrow books on a distributed system. The users can display all books in the library, borrow books, extend or cancel their reservations. 

## Requirements
To run the project, you need:
- [Python](https://www.python.org/)
- [Pipenv](https://pipenv.pypa.io/en/latest/). 
- [Docker](https://www.docker.com/)

## Running the project
First, activate the pipenv and launch the shell.
```bash
pipenv install
pipenv shell
```
Next, you need to launch the docker network and nodes. To do so, use docker compose
```bash
docker compose up -d
```
Finally, run the python script.
```bash
python main.py
```


## Database schema
```mermaid
---
title: library_reservation.
---
classDiagram 
    direction LR
    class books {
        book_id: UUID (PRIMARY KEY)
        author: text
        title: text
    }
    
    class reservations {
        user: text (PRIMARY KEY)
        reservation_id: UUID (PARTITION KEY)
        book_id: UUID
        due_date: timestamp
    }
    
    class borrowed {
        book_id: UUID (PRIMARY KEY)
    }

    class resource_locks {
        resource_id: UUID (PRIMARY KEY)
        lock_time: timestamp
        locked_by: text
    }
```

## Stress Tests Results:
Tests are performed on 1000 randomly generated books.
1. Stress test 1 - the test itself run pretty smoothly. The task is simple, and the book was borrowed only once - the system prevented it from being borrowed again. 
![test 1 results](test_1.png)
2. Stress test 2 - this test took quite a lot longer to finish. I believe that it might come from the sheer size and random choices included in the test. There are also more 'true' requests commited - the system needs to manage more than 1 book
![test 2 results](test_2.png)
3. Stress test 3 - this test was much more insightful in it's result. The first attemtps on what I thought was a finished project shown how the locking mechanism was fauty, and did not work as intented.
![test 3 bad tesults](test_3_bad.png)
The fix was using lightweight transactions - locking the resources in a table with IF NOT EXISTS cause, and a signature of which user adds it. It adds some time to the operation, but it solves the problem of overbooking.
![test 3 final results](test_3.png)
As we can see however, due to the CAP theorem there still exist some discrepancies in the borrowed books.
