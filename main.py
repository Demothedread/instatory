import os
import sys
import sqlite3
import base64
import json
import requests
import logging
import openai
from datetime import datetime
import shutil
from tenacity import retry, wait_random_exponential, stop_after_attempt

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Set your OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Directory and database configurations
DB_NAME = 'database.sqlite3'
DATA_DIR = 'data'
UPLOADS_DIR = os.path.join(DATA_DIR, 'images', 'uploads')
INVENTORY_IMAGES_DIR = os.path.join(DATA_DIR, 'images', 'inventory')
TEMP_DIR = os.path.join(DATA_DIR, 'temp')
EXPORTS_DIR = os.path.join(DATA_DIR, 'exports')

def initialize_database():
    """Initialize the database and create the products table if it doesn't exist."""
    try:
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT,
                    image_url TEXT UNIQUE,
                    category TEXT,
                    material TEXT,
                    color TEXT,
                    dimensions TEXT,
                    origin_source TEXT,
                    import_cost REAL,
                    retail_price REAL,
                    key_tags TEXT
                )
            ''')

            # Check if key_tags column exists, if not, add it
            cursor.execute("PRAGMA table_info(products)")
            columns = [column[1] for column in cursor.fetchall()]
            if 'key_tags' not in columns:
                cursor.execute("ALTER TABLE products ADD COLUMN key_tags TEXT")

            conn.commit()
            logging.info("Database initialized successfully.")
    except sqlite3.Error as e:
        logging.error(f"Error initializing database: {e}")

def encode_image_to_base64(image_path):
    """Encode an image to a base64 string."""
    try:
        with open(image_path, 'rb') as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except FileNotFoundError:
        logging.error(f"Image file not found: {image_path}")
        return None
    except Exception as e:
        logging.error(f"Error encoding image {image_path}: {str(e)}")
        return None

@retry(wait=wait_random_exponential(min=1, max=40), stop=stop_after_attempt(6))
def analyze_image(image_base64):
    """Analyze an image using OpenAI's GPT-4 model and return product features."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {openai.api_key}"
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": "You are an assistant that helps catalog and describe African import products for inventory."
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Given an image of a product we sell, analyze the item and generate a JSON output with the following fields: "
                            "- \"name\": A descriptive name. "
                            "- \"description\": A concise and detailed product description in bullet points. "
                            "- \"category\": One of [\"Beads\", \"Stools\", \"Bowls\", \"Fans\", \"Totebags\", \"Home Decor\"]. "
                            "- \"material\": Primary materials. "
                            "- \"color\": Main colors. "
                            "- \"dimensions\": Approximate dimensions. "
                            "- \"origin_source\": Likely origin based on style. "
                            "- \"import_cost\": Best estimated import price in USD or 'null'. "
                            "- \"retail_price\": Best estimated retail price in USD or 'null'. "
                            "- \"key_tags\": Important keywords/phrases for product discovery."
                            "Provide only the JSON output without any markdown formatting."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ],
        "max_tokens": 700
    }

    try:
        logging.debug("Sending request to OpenAI API")
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        logging.debug(f"OpenAI API response status: {response.status_code}")
        response_text = response.json()['choices'][0]['message']['content'].strip()
        logging.debug(f"OpenAI API response text: {response_text}")

        # Remove any markdown formatting if present
        if response_text.startswith("```json"):
            response_text = response_text.split("\n", 1)[1].rsplit("\n", 1)[0]

        # Replace single quotes with double quotes for valid JSON
        response_text = response_text.replace("'", '"')

        return json.loads(response_text)
    except requests.exceptions.RequestException as e:
        logging.error(f"Request failed: {e}")
        return {}
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response: {e}")
        logging.error(f"Response text: {response_text}")
        return {}
    except Exception as e:
        logging.error(f"Unexpected error in analyze_image: {str(e)}")
        return {}

def insert_product_info(cursor, product_info, img_path):
    """
    Insert product information into the products table.

    Args:
        cursor: SQLite cursor object.
        product_info (dict): Dictionary containing product details.
        img_path (str): Path to the image file.

    Raises:
        KeyError: If any required field is missing in product_info.
    """
    required_keys = [
        'name', 'description', 'category', 'material',
        'color', 'dimensions', 'origin_source', 'import_cost', 'retail_price', 'key_tags'
    ]

    for key in required_keys:
        if key not in product_info:
            raise KeyError(f"Missing required field: {key}")

    # Convert list fields to strings
    description = '\n'.join(product_info['description']) if isinstance(product_info['description'], list) else product_info['description']
    key_tags = ', '.join(product_info['key_tags']) if isinstance(product_info['key_tags'], list) else product_info['key_tags']

    try:
        cursor.execute('''
            INSERT INTO products
            (name, description, image_url, category, material, color, dimensions, origin_source, import_cost, retail_price, key_tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product_info['name'],
            description,
            img_path,
            product_info['category'],
            product_info['material'],
            product_info['color'],
            product_info['dimensions'],
            product_info['origin_source'],
            product_info['import_cost'],
            product_info['retail_price'],
            key_tags
        ))
        logging.info(f"Successfully inserted product info for image: {img_path}")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert product info into database: {e}")

def process_uploaded_images():
    """Process uploaded images recursively, create a new directory, and save the processed images."""
    logging.info("Starting to process uploaded images")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # Retrieve existing image URLs from the database to avoid duplicates
        cursor.execute("SELECT image_url FROM products")
        existing_images = set(row[0] for row in cursor.fetchall())

        # Create a new directory for this batch of processed images
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        batch_dir = os.path.join(INVENTORY_IMAGES_DIR, timestamp)
        os.makedirs(batch_dir, exist_ok=True)
        logging.info(f"Created batch directory: {batch_dir}")

        # Walk through the uploads directory recursively
        for root, dirs, files in os.walk(UPLOADS_DIR):
            logging.info(f"Traversing directory: {root}")
            for filename in files:
                logging.info(f"Found file: {filename}")
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp')):
                    image_path = os.path.join(root, filename)
                    logging.info(f"Processing image: {image_path}")
                    encoded_image = encode_image_to_base64(image_path)
                    if encoded_image:
                        # Maintain relative path for the new image location
                        relative_path = os.path.relpath(root, UPLOADS_DIR)
                        if relative_path == '.':
                            relative_path = ''
                        new_image_dir = os.path.join(batch_dir, relative_path)
                        os.makedirs(new_image_dir, exist_ok=True)
                        new_image_path = os.path.join(new_image_dir, filename)

                        if new_image_path not in existing_images:
                            product_info = analyze_image(encoded_image)
                            if product_info:
                                try:
                                    shutil.move(image_path, new_image_path)
                                    insert_product_info(cursor, product_info, new_image_path)
                                    logging.info(f"Successfully processed and inserted product from image: {filename}")
                                except KeyError as e:
                                    logging.error(f"Error inserting product info for {filename}: {e}")
                            else:
                                logging.error(f"Failed to analyze image: {filename}")
                        else:
                            logging.info(f"Image already exists in database: {filename}")
                    else:
                        logging.warning(f"Could not encode image: {filename}")
    logging.info(f"Finished processing images. Processed images saved in {batch_dir}.")

def main():
    """Main function to initialize the database and process images."""
    logging.info("Starting main function")
    initialize_database()

    if len(sys.argv) > 1 and sys.argv[1] == '--process-images':
        logging.info("Processing images flag detected")
        process_uploaded_images()
    else:
        logging.warning("No valid command-line argument provided. Use --process-images to process uploaded images.")

    logging.info("Main function completed")

if __name__ == "__main__":
    main()
