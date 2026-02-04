import sqlite3

from websockets import connect

db = sqlite3.connect('/home/gluck/Urology.dasmix')

with open('best_ids.txt') as in_file:
    best_ids = in_file.read().splitlines()

BATCH_SIZE = 20000

for i in range(0, len(best_ids), BATCH_SIZE):
    print(i, i+BATCH_SIZE, len(best_ids[i:i+BATCH_SIZE]))
    id_str = best_ids[i:i+BATCH_SIZE]
    db.execute(f'update identification set is_preferred = 1 where id in ({", ".join(id_str)})')
    db.commit()