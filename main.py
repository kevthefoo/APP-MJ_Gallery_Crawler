import subprocess, os, json, requests, time, datetime
from selenium import webdriver
import urllib.request
import boto3

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

from lib.reverseTimestamp import generate_reverse_timestamped_filename

# Load the environment variables from the .env file (For local enviroment)
from dotenv import load_dotenv
load_dotenv()

# Load Driver's Configuration
CHROME_PATH = os.getenv("CHROME_BROWSER_PATH")
USER_PROFILE_PATH = os.getenv("USER_PROFILE_PATH")
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
BUCKET_NAME = os.getenv('BUCKET_NAME')
MEETJOHNNY_API_ENDPOINT = os.getenv('MEETJOHNNY_API_ENDPOINT')

# Launch Chrome in debug mode
try:
    response = requests.get(f'http://127.0.0.1:9222/json')
    if response.status_code == 200:
        print(f"Chrome is already running on port 9222")
    else:
        raise Exception("Chrome not running")
except:
    subprocess.Popen([CHROME_PATH, f'--remote-debugging-port=9222', f'--user-data-dir={USER_PROFILE_PATH}'])
    print(f"Launched Chrome on port 9222")

# --------------------------------------Initialize Selenium--------------------------------------

chrome_options = webdriver.ChromeOptions()
chrome_options.add_experimental_option("debuggerAddress", f"127.0.0.1:9222")
driver = webdriver.Chrome(options=chrome_options)

# --------------------------------------Initialize Selenium--------------------------------------

s3 = boto3.client('s3', aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)

# --------------------------------------Start Scraping--------------------------------------

TARGET_URL = "https://www.midjourney.com/"
driver.get(TARGET_URL)

time.sleep(5)

# Download an image
def download_image(url, file_path, job_id):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('Accept-Encoding', 'gzip, deflate, br, zstd')
    req.add_header('authority', 'cdn.midjourney.com')
 
    attempt = 0
    for attempt in range(30):
        try:
            response = urllib.request.urlopen(req)
        except:
            print('System: Request failed...\n')
            attempt += 1
            time.sleep(5)
        else:
            print(f"\nSystem: Try {attempt+1} times to get the image...\n")  
            with open(file_path, 'wb') as file:
                file.write(response.read())
            return True
        
    remove_image_from_metadata(job_id)
    print(f"System: Failed to download the image {url}\n")
    return False

# Upload an image to S3
def upload_to_s3(file_path, bucket_name, object_name, metadata, job_id, file_type):
    try:
        s3.upload_file(file_path, bucket_name, object_name, ExtraArgs={
                'ContentType': f'image/{file_type}',
                'Metadata': metadata
            })
    except Exception as e:
        remove_image_from_metadata(job_id)
        print(f"Error uploading {file_path} to S3: {e}\n")
    else:
        print(f"Uploaded {file_path} to {bucket_name}/{object_name}\n")
    finally:
        os.remove(file_path)
        print(f"Deleted local file {file_path}\n")

# Remove the image from the metadata
def remove_image_from_metadata(job_id):
    with open('data/data.json', 'r') as f:
        data = json.load(f)
    
    if job_id in data:
        del data[job_id]
        with open('data/data.json', 'w') as file:
            json.dump(data, file, indent=4)

# Update the metadata
def update_metadata(file_path, bucket_name, object_name):
    try:
        s3.upload_file(file_path, bucket_name, object_name )
        print(f"Uploaded {file_path} to {bucket_name}/{object_name}\n")
    except Exception as e:
        print(f"Error uploading {file_path} to S3: {e}\n")

# Send Post Request to the MeetJohnny website API
def send_data():
    with open('data/data.json', 'r') as file:
        data = json.load(file)

    url = MEETJOHNNY_API_ENDPOINT  # Replace with your actual endpoint
    headers = {'Content-Type': 'application/json'}

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()  # Raise an exception for HTTP errors
        print(f"System: Successfully sent POST request. Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"System: Failed to send POST request. Error: {e}")

# --------------------------------------Start Scraping--------------------------------------

first_job_cards = driver.find_element(By.XPATH, "//div[contains(@class, 'container/jobCard')]")
first_job_cards.click()
time.sleep(5)
body = driver.find_element(By.TAG_NAME, "body")
time.sleep(5)

# Get today's date
date = datetime.date.today().strftime("%Y-%m-%d")

break_count = 0
while True:
    # Break the loop after 10 same jobs founded iterations
    if break_count >= 10:
        send_data()
        print("System: Scraping completed...")
        break

    # Find the image URLs and Job ID
    images = driver.find_elements(By.CSS_SELECTOR, "img.absolute.w-full.h-full")
    webp_url = images[0].get_attribute("src")
    jpg_url = images[1].get_attribute("src")
    job_id = jpg_url.split("/")[-2]
    print(f"JPG URL: {jpg_url}\n")
    print(f"Job ID: {job_id}\n")

    with open(f"data/data.json", "r") as f:
        data = json.load(f)
    
    if job_id in data:
        break_count+=1
        print("Job already exists in the database\n---------------------------------\n")
        body.send_keys(Keys.ARROW_RIGHT)
        time.sleep(5)
        continue

    # Find the prompt
    prompt_box = driver.find_element(By.ID, "lightboxPrompt")
    prompt = prompt_box.find_element(By.TAG_NAME, "p").text
    print(f"Prompt: {prompt}\n")

    # Find the parameters
    ratio = '1:1'
    tags = prompt_box.find_elements(By.TAG_NAME, "button")
    for _ in tags:
        tag_text = _.text.replace("\n", "").strip()
        if 'ar ' in tag_text:
            width=tag_text.replace('--ar ', '').split(':')[0]
            height=tag_text.replace('ar ', '').split(':')[1]
            ratio = f"{width}:{height}"
        if tag_text:
            print(f"Button: {tag_text}")

    reverse_timestamp = generate_reverse_timestamped_filename()
    
    with open(f"data/data.json", "w") as f:
        data[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "tags": [_.text.replace("\n", "").strip() for _ in tags],
            "webp_url": webp_url,
            "jpg_url": jpg_url,
            "ratio": ratio,
            "object_name": f"{reverse_timestamp}/{job_id}",
            "timestamp": int(time.time()),
        }
        json.dump(data, f, indent=4)

    metadata={
        "job_id": job_id,
        "prompt": prompt,
        "tags": ','.join([_.text.replace("\n", "").strip() for _ in tags],),
        "webp_url": webp_url,
        "jpg_url": jpg_url,
    }


    # Download the webp image
    file_path = f"data/images/{job_id}.webp"
    response = download_image(webp_url, file_path, job_id)

    if response == True:
        # Upload the image to S3
        upload_to_s3(file_path, BUCKET_NAME, f"{reverse_timestamp}/{job_id}.webp", metadata, job_id, file_type="webp")

    for second in range(20):
        print(f"System: Please wait for {20-second} seconds...")
        time.sleep(1)

    # Download the jpeg image
    file_path = f"data/images/{job_id}.jpg"
    response = download_image(jpg_url, file_path, job_id)

    if response == True:
        # Upload the image to S3
        upload_to_s3(file_path, BUCKET_NAME, f"{reverse_timestamp}/{job_id}.jpg", metadata, job_id, file_type="jpeg")
   
    # Update the metadata
    update_metadata("data/data.json", BUCKET_NAME, 'data.json')

    print("---------------------------------\n")
    body.send_keys(Keys.ARROW_RIGHT)

    for second in range(60):
        print(f"System: Please wait for {60-second} seconds...")
        time.sleep(1)