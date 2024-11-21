import subprocess, os, json, requests, time
from selenium import webdriver
import urllib.request
import boto3

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

# Load the environment variables from the .env file (For local enviroment)
from dotenv import load_dotenv
load_dotenv()

# Load Driver's Configuration
CHROME_PATH = os.getenv("CHROME_BROWSER_PATH")
USER_PROFILE_PATH = os.getenv("USER_PROFILE_PATH")
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')

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
BUCKET_NAME = 'mjgallery'

# --------------------------------------Start Scraping--------------------------------------

TARGET_URL = "https://www.midjourney.com/explore?tab=top"
driver.get(TARGET_URL)

time.sleep(5)

# Download an image
def download_image(url, file_path):
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36')
    req.add_header('Accept', 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7')
    req.add_header('Accept-Language', 'en-US,en;q=0.9')
    req.add_header('authority', 'cdn.midjourney.com')

    attempt = 0
    for attempt in range(15):
        try:
            response = urllib.request.urlopen(req)
        except:
            print('System: Request failed...\n')
            attempt += 1
            time.sleep(5)
        else:
            print(f"System: Try {attempt+1} times to get the image...\n")  
            with open(file_path, 'wb') as file:
                file.write(response.read())
            break


# Upload an image to S3
def upload_to_s3(file_path, bucket_name, object_name):
    try:
        s3.upload_file(file_path, bucket_name, object_name, ExtraArgs={
                'ContentType': 'image/jpeg',
            })
        print(f"Uploaded {file_path} to {bucket_name}/{object_name}")
    except Exception as e:
        print(f"Error uploading {file_path} to S3: {e}")

first_job_cards = driver.find_element(By.XPATH, "//div[contains(@class, 'container/jobCard')]")
first_job_cards.click()
time.sleep(5)
body = driver.find_element(By.TAG_NAME, "body")
time.sleep(5)

while True:
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
        print("Job already exists in the database\n---------------------------------\n")
        body.send_keys(Keys.ARROW_RIGHT)
        time.sleep(5)
        continue

    # Find the prompt
    prompt_box = driver.find_element(By.ID, "lightboxPrompt")
    prompt = prompt_box.find_element(By.TAG_NAME, "p").text
    print(f"Prompt: {prompt}\n")

    # Find the parameters
    tags = prompt_box.find_elements(By.TAG_NAME, "button")
    for _ in tags:
        tag_text = _.text.replace("\n", "").strip()
        if tag_text:
            print(f"Button: {tag_text}")

    with open(f"data/data.json", "w") as f:
        data[job_id] = {
            "job_id": job_id,
            "prompt": prompt,
            "tags": [_.text.replace("\n", "").strip() for _ in tags],
            "webp_url": webp_url,
            "jpg_url": jpg_url,
        }
        json.dump(data, f, indent=4)

    # Download the image
    file_path = f"data/images/{job_id}.jpg"
    download_image(jpg_url, file_path)

    # Upload the image to S3
    upload_to_s3(file_path, BUCKET_NAME, f"{job_id}.jpg")


    print("---------------------------------\n")
    body.send_keys(Keys.ARROW_RIGHT)
    time.sleep(60)