# Purpose

The following script is designed to aid PokemonGo players in keeping and updating a database of Gold gyms. Currently, a player has a view the 1000 gyms they most recently interacted with as a cap. For players aiming to accumulate a larger number of Gold badges, this cap is inconvenient as gyms start to "fall off".

- *Disclaimer: Functionality has ONLY been tested on iPhone models*

***

## Pre-Requisites
After cloning this repo locally, there are tasks to complete before running the script.

##### 1. SetUp
Run the executable `setup.sh` which will
* Create a **badges** directory and

* Create a virtual environment with all the required libraries.

##### 2. Google Sheet
This is arguably the most tedious step.
* The user must create a Google Sheet with the following headers:
    
    > image | title | style | victories | defended | treats | coordinates | city | county | state

* The script will populate all but two fields. The fields *title* and *coordinates* must be **manually** populated for each row/gym. The *title* should use all lowercase and *coordinates* should be comma-separated with no space in between i.e. 40.758186,-73.985585. (Suggestion: Access **Ingress** maps for coordinates.)

* Follow the process outlined for [GSPREAD](https://docs.gspread.org/en/latest/oauth2.html) in order to enable API Access to your Google Sheet. After understanding and completing the process, the created json file should be saved in the `subfiles` directory.

#### 3. Update Variables
Open `subfiles/variables.env` and update each value. <br>

***

## The Process

Each image is scanned from **DOWNLOADS** and to extracts fields to populate the user's Google Sheet. During each iteration, if reading errors occur, the user is prompted to manually type specified values. Then, the appropriate row is updated and a local file `subfiles/log` is updated. Each image is relocated to **BADGES** using the naming convention `IMG_####.PNG`. Lastly, the user is given the option to sort their Google Sheet.

***

## Usage

The process has two options:

#### Scan
This flag scans all images in Downloads folder.
> ./gyms.py -s

#### Update
This flag will update one gym with new values from a recent screenshot.
> ./gyms.py -u \<new_image> \<id_to_update>
