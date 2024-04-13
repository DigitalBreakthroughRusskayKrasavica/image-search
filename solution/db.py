import os
import numpy as np
import os
import clickhouse_connect 
from PIL import Image
import ai_model

class DB:
    def __init__(self, model): 
        self.model = model
        self.client = clickhouse_connect.get_client(
            host=os.getenv('CLICKHOUSE_HOST') or None, 
            port=os.getenv('CLICKHOUSE_PORT') or None,
            username=os.getenv('CLICKHOUSE_USERNAME') or None, 
            password=os.getenv('CLICKHOUSE_PASSWORD') or None,
        )
        print('connected to clickhouse')
        self.client.command('''
        CREATE TABLE IF NOT EXISTS museum_items (
            object_id Integer, 
            img_name String, 
            name Nullable(String), 
            description Nullable(String), 
            group String,
            image_embedding Array(Float32)
        ) ENGINE MergeTree ORDER BY object_id
        ''')
    
    def insert_museum_items(self, df):
        data = [] 
        for index, row in df.iterrows(): 
            image = Image.open(row.path)
            emb = self.model.encode_images(image).tolist()
            row = row.replace({np.nan: None}).to_dict()
            data.append([row['object_id'], row['img_name'], row['name'], row['description'], row['group'], emb])
        self.client.insert('museum_items', data, column_names='*')

        print('inserted', self.client.command('select count(*) from museum_items'), ' museum items')

    def search_similar(self, img: str | Image.Image):
        if isinstance(img, str): 
            img = Image.open(img) 
        emb = self.model.encode_images(img).tolist()
        parameters = {'query_embedding': emb}
        res = self.client.query('''
            SELECT object_id, img_name, L2Distance(image_embedding, {query_embedding:Array(Float32)}) as dist 
            FROM museum_items 
            ORDER BY dist ASC
            LIMIT 10
        ''', parameters=parameters)
        return [os.path.join(str(row[0]), row[1]) for row in res.result_rows]


if __name__ == '__main__': 
    db = DB(ai_model.large_clip)
    db.insert_museum_items(ai_model.df[:ai_model.IMAGE_SEARCH_SUBSET_N])