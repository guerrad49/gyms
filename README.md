# Purpose

The following script is designed to aid PokemonGo players in keeping and updating a database of Gold gyms. Currently, a player has a view the 1000 gyms they most recently interacted with as a cap. For players aiming to accumulate a larger number of Gold badges, this cap is inconvenient as gyms start to "fall off".

- *Disclaimer: Functionality has ONLY been tested on iPhone models*

***

## Pre-Requisites
After cloning this repo locally, there are several tasks to complete before running the script.

##### 1. Badges
Create a directory where you will store all your screenshots of gyms to a path of your chosing. The path you chose will not affect performance.

##### 2. Variables
Make sure the name of `subfiles/variables_template.txt` and the value of **VARS_FILE** in `gyms.py (line 28)` match. For the remainding of this README, we'll assume both have the name `variables.txt`.

##### 3. Environment
Use the command line to create a virtual environment and install requirements.
```
   $ python3 -m venv <name_of_your_venv>
   $ source <name_of_your_venv>/bin/activate
   $ pip install -r requirements.txt
   $ deactivate
```

##### 4. Google Sheet
This is arguably the most tedious step.
* The user must create a Google Sheet with the following headers:
    
    > image | title | style | victories | defended | treats | coordinates | city | county | state

* The script will populate all but two fields. The fields *title* and *coordinates* must be **manually** populated for each row/gym. The *title* should use all lowercase and *coordinates* should be comma-separated with no space in between i.e. 40.758186,-73.985585. (Suggestion: Access **Ingress** maps for coordinates.)

* Follow the process outlined for [GSPREAD](https://docs.gspread.org/en/latest/oauth2.html) in order to enable API Access to your Google Sheet. After understanding and completing the process, the created json file should be saved in the `subfiles` directory.

#### 5. Update Variables
Open `subfiles/variables.txt` and update all five values. <br>
*Note: You can choose a custom folder for **DOWNLOADS_PATH**. Files are only stored here until they are processed and relocated.*

***

## The Process

Each image is scanned from **DOWNLOADS_PATH** and to extracts fields to populate the user's Google Sheet. During each iteration, if reading errors occur, the user is prompted to manually type specified values. Then, the appropriate row is updated and a local file `subfiles/log` is updated. Each image is relocated to **BADGES_PATH** using the naming convention `IMG_####.PNG`. Lastly, the user is given the option to sort their Google Sheet.

***

## Usage

The process has two options:

#### Scan
This flag scans all images in Downloads folder.
> ./gyms.py -s

#### Update
This flag will update one gym with new values from a recent screenshot.
> ./gyms.py -u \<new_image> \<id_to_update>
