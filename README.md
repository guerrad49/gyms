# Purpose

The following script is designed to aid PokemonGo players in keeping and updating a database of Gold gyms. Currently, a player has a view the 1000 gyms they most recently interacted with as a cap. For players aiming to accumulate a larger number of Gold badges, this cap is inconvenient as gyms start to "fall off".

- *Disclaimer: Functionality has ONLY been tested on iPhone*

***

## Pre-Requisites

#### Clone Repository
* After cloning this repo, you will need to manually created a directory where you will store your screenshots of gyms. Update the variable **BADGES_PATH** in <span style="color:cyan">*variables_template.txt*</span> accordingly. The rest of the variables will be updated throughout the next steps.

#### Create Virtual Environment
> python3 -m venv <name_of_virtualenv>

* After doing so, be sure to add all the items in <span style="color:cyan">*requirements.txt*</span> to the virtual environment.

#### Google Sheet
* The user must create a Google Sheet with the following headers:
    
    > image | title | style | victories | defended | treats | coordinates | city | county | state

  In <span style="color:cyan">*variables_template.txt*</span>, update the variable **GOOGLE_SHEET_NAME**.

* The columns *title* and *coordinates* must be **manually** populated for each row/gym. The *title* should use all lowercase for now and *coordinates* should be comma-separated with <u>no</u> space in between i.e. 40.758186,-73.985585. (Suggestion: Access <span style="color:green">**Ingress**</span> maps.)

* Follow the process outlined for [GSPREAD](https://docs.gspread.org/en/latest/oauth2.html) in order to enable API Access to your Google Sheet. After understanding and completing the process, the created json file should be saved in the same local directory as all the scripts. In <span style="color:cyan">*variables_template.txt*</span>, update the variable **JSON_KEY_FILE** accordingly.

#### Downloads Folder
* Update the variable **DOWNLOADS_PATH** in <span style="color:cyan">*variables_template.txt*</span>. Note, it's not essential to use your local Downloads folder. However, when sending images from iPhone to Mac via AirDrop, the images are automatically directed to Downloads. You can choose a different folder for this variable as files are only stored here initially before they are processed.

***

## The Process

Images are first tranferred from Downloads folder to Badges folder are renamed in ascencing order with the format IMG_####.PNG. Each image is then scanned for fields and the gym's location is populated using the Google Sheet field *coordinates*. During each iteration, if reading errors occur, the user is prompted to manually type specified values. Then, the appropriate row is updated and a local file <span style="color:cyan">*logger.log* </span> is created/updated. Lastly, images are relocated and the user is given the option to sort the Google Sheet.

***

## Usage

The process has three options:

#### Scan
This flag scans all images in Downloads folder.
> ./gyms.py variables_template.txt -s

#### Update
This flag will update one gym with new values from a recent screenshot.
> ./gyms.py variables_template.txt -u \<new_image> \<id_to_update>

#### Test
This flag will allow the user to scan past images in test mode i.e. no information is written to Google Sheet.
> ./gyms.py variables_template.txt -t


