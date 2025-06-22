### Purpose

This package aims to aid PokemonGo players build and maintain a database of gyms with **GOLD** status. The in-game cap of 1000 most recent gyms was a key motivation for this development.

- *Disclaimer: Functionality has ONLY been tested on iPhone models iSE, i11, i15.*

***

### Pre-Requisites
Clone this repo and follow the steps below.

#### 1. SetUp
Run the executable `setup.sh` which will
* Create a **badges** directory and
* Create a virtual environment with all the required python libraries.

#### 2. Google Sheet
This is arguably the most tedious section.
* The user must create a Google Sheet with the following headers:
    
    > uid | title | model | style | victories | defended | treats | coordinates | city | county | state

* The `scan.py` script will populate all BUT two fields. The fields *title* and *coordinates* must be **manually** populated for each row/gym. The *title* should use all lowercase and *coordinates* should be comma-separated with no space in between i.e. 40.758186,-73.985585. (Suggestion: Access **Ingress** maps for coordinates.)

* Follow the process outlined for [GSPREAD](https://docs.gspread.org/en/latest/oauth2.html) in order to enable API Access to your Google Sheet. After understanding and completing the process, the created json file should be saved in the `requirements` directory.

#### 3. Environment Variables
Open `requirements/variables_template.env`, update each value and rename the file to `variables.env`. *Warning: Not renaming this file will raise errors when running main script.*<br>

The directory structure should now look like below.
```
.
├── .venv
├── badges
├── PokemonGo
│    ├── __init__.py
│    ├── exceptions.py
│    ├── gym.py
│    ├── image.py
│    ├── sheet.py
│    └── utils.py
├── requirements
│    ├── requirements.txt
│    ├── variables.env
│    └── /your/json/key/.json
├── tests
│    ├── __init__.py
│    ├── gym_test.py
│    ├── image_test.py
│    └── images
├── README.md
├── scan.py
└── setup.sh
```

***

### The Process

Each image is scanned from ~/Downloads<sup>*</sup> directory and extracts image properties, badge statistics, and location details. During each iteration, if reading errors occur, the user is prompted for manual input. The corresponding row in user's Google Sheet and a local log (under `requirements`) are both updated. Each image is relocated to `badges` directory using the naming convention `IMG_####.PNG`. Lastly, the Google Sheet is sorted by geolocation.

<sup>*</sup> <font size="2">This choice is convenient since using AirDrop will automatically send screenshots to this directory. However, the user can change this by modifying `utils.py`.</font>

***

### Usage

Activate the virtual environment and run the script.
```
$ source .venv/bin/activate
$ (.venv) ./scan.py
```

Consider having your Google spreadsheet open to see the automation.

Lastly, there is an option to update badge statistics. To do so, run as follows:
```
$ (.venv) ./scan.py -u
```
However, note that this option **only** handles updates. Hence, scanning new badges in this option will not work.

***

### Testing

Several unit tests have been written under `tests` directory. Within the virtual environment, the user can run all tests or a particular set of tests as shown below. Note the verbose flag.

```
(.venv) $ pytest -v tests
(.venv) $ pytest -v tests/gym_test.py
```

For additional details on `pytest`, see the [documentation](https://docs.pytest.org/en/8.2.x/).