### Purpose

This package aims to aid PokemonGo players build and maintain a database of gyms with **GOLD** status. The in-game cap of 1000 most recent gyms was a key motivation for this development.

- *Disclaimer: Functionality has ONLY been tested on iPhone models iSE, i11, i15.*

***

### Pre-Requisites
Clone this repo and follow the steps below.

##### 1. SetUp
Run the executable `setup.sh` which will
* Create a **badges** directory and
* Create a virtual environment with all the required python libraries.

##### 2. Google Sheet
This is arguably the most tedious section.
* The user must create a Google Sheet with the following headers:
    
    > uid | title | model | style | victories | defended | treats | coordinates | city | county | state

* The `main.py` script will populate all BUT two fields. The fields *title* and *coordinates* must be **manually** populated for each row/gym. The *title* should use all lowercase and *coordinates* should be comma-separated with no space in between i.e. 40.758186,-73.985585. (Suggestion: Access **Ingress** maps for coordinates.)

* Follow the process outlined for [GSPREAD](https://docs.gspread.org/en/latest/oauth2.html) in order to enable API Access to your Google Sheet. After understanding and completing the process, the created json file should be saved in the `subfiles` directory.

#### 3. Environment Variables
Open `subfiles/variables.env` and update each value. <br>

***

### The Process

Each image is scanned from `Downloads` directory and extracts image properties, badge statistics, and location details. During each iteration, if reading errors occur, the user is prompted for manual input. The corresponding row in user's Google Sheet and a local log (under `subfiles`) are both updated. Each image is relocated to `badges` directory using the naming convention `IMG_####.PNG`. Lastly, the Google Sheet is sorted by geolocation.

***

### Usage

Activate the virtual environment.
```
$ source .venv/bin/activate
```
NOTE: Under maintenance.

***

### Testing

Several unit tests have been written under `tests` directory. Within the virtual environment, the user can run all tests or a particular set of tests as shown below. Note the verbose flag.

```
(.venv) $ pytest -v tests
(.venv) $ pytest -v tests/gym_test.py
```

For additional details on `pytest`, see the [documentation](https://docs.pytest.org/en/8.2.x/).