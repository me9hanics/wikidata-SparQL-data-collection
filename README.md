# SparQL Wikidata data collection from Wikipedia profiles 
A file with functions to help fetch various data of personalities (and other entities) from Wikidata, and a notebook showing how to use them.

## Usage

The functions are in the ```functions.py``` file, which you can easily import after downloading 

### Get the information of someone, e.g. van Gogh from Wikidata

Using the ```get_all_person_info``` function (other options are *get_person_info* and *get_person_locations* which include less information)


```python
import functions as f

van_gogh_response = f.get_all_person_info("Van Gogh")
van_gogh_response
```

The returned response:

```
    {'name': 'Van Gogh',
     'birth_place': 'Zundert',
     'birth_date': '1853-03-30T00:00:00Z',
     'death_date': '1890-07-29T00:00:00Z',
     'death_place': 'Auvers-sur-Oise',
     'gender': 'male',
     'citizenship': 'Kingdom of the Netherlands',
     'occupation': ['drawer', 'printmaker', 'painter'],
     'work_locations': [{'location': 'Saint-Rémy-de-Provence',
       'start_time': '1889-05-01T00:00:00Z',
       'end_time': '1890-05-01T00:00:00Z',
       'point_in_time': None},
      {'location': 'The Hague',
       'start_time': '1881-12-01T00:00:00Z',
       'end_time': '1883-09-01T00:00:00Z',
       'point_in_time': None},

        ...

      {'location': 'Maison Van Gogh',
       'start_time': '1879-08-01T00:00:00Z',
       'end_time': '1880-10-01T00:00:00Z',
       'point_in_time': None}]}
```


Print some information from the dictionary:


```python
print(f"Birthplace: {van_gogh_response['birth_place']}, deathplace: {van_gogh_response['death_place']}")
print(f"Birthyear: {f.find_year(van_gogh_response['birth_date'])}, deathdate: {f.find_year(van_gogh_response['death_date'])}")
print(f"Gender: {van_gogh_response['gender']}, citizenship: {van_gogh_response['citizenship']}, occupations: {str(van_gogh_response['occupation']).strip('[]')}")
print()
print("Work locations:")
print(f.get_places_from_response(van_gogh_response))
```

    Birthplace: Zundert, deathplace: Auvers-sur-Oise
    Birthyear: 1853, deathdate: 1890
    Gender: male, citizenship: Kingdom of the Netherlands, occupations: 'drawer', 'printmaker', 'painter'
    
    Work locations:
    ['Saint-Rémy-de-Provence', 'The Hague', 'Ramsgate', 'City of Brussels', 'Etten-Leur', 'Dordrecht', 'Nuenen', 'Paris', 'Auvers-sur-Oise', 'Van Gogh House', 'Emmen', 'London', 'Amsterdam', 'Arles', 'Hoogeveen', 'Antwerp', 'Borinage', 'Tilburg', 'Maison Van Gogh']
    

For a nicer display, we can print each part manually, with residence period too:


```python
places_str = f.get_places_with_years_from_response(van_gogh_response)
places_list = f.stringlist_to_list(places_str)
for place in places_list:
    name,period = place.replace(",", " and ").split(":")
    print(f"{name}, between {period}")
```

    Saint-Rémy-de-Provence, between 1889-1890
    The Hague, between 1881-1883 and 1869-1873
    Ramsgate, between 1876-1876
    City of Brussels, between 1880-1881
    Etten-Leur, between 1881-1881 and 1876-1876
    Dordrecht, between 1877-1877
    Nuenen, between 1883-1885
    Paris, between 1875-1876 and 1886-1888
    Auvers-sur-Oise, between 1890-1890
    Van Gogh House, between 1883-1883
    London, between 1873-1875
    Amsterdam, between 1877-1878
    Arles, between 1888-1889
    Hoogeveen, between 1883-1883
    Antwerp, between 1885-1886
    Borinage, between 1878-1879
    Tilburg, between 1866-1868
    Maison Van Gogh, between 1879-1880
    

We could get all this information by using a SparQL query, simplifying the process. Let's see how an example of a SparQL query:
  
  ```sparql
    person_name = "Vincent van Gogh"
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?workLocationLabel ?startTime ?endTime ?pointInTime ?citizenshipLabel ?occupationLabel WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P19 ?placeOfBirth.
      ?person wdt:P569 ?dateOfBirth.
      OPTIONAL { ?person wdt:P27 ?citizenship. }
      OPTIONAL { ?person wdt:P106 ?occupation. }
      OPTIONAL {
        ?person p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ''' % person_name.replace('"', '\"')
  ```

What does each part do?

The ```SELECT``` row declaring the variables with names (with questionmarks in front) and only the ones that will be returned in the response (see how ?occupation is not included, but ?occupationLabel is). Some variables get a "Label" suffix, they represent the human-readable representative name of the person, whereas the "original" variable stores the identifier (like "Budapest" is the label and "Q1781" is its identifier). The ```SERVICE``` line helps to put these values in the Label variables, only having to include this line instead of a line for every label, this is a special feature by Wikidata. This is described [here](https://en.wikibooks.org/wiki/SPARQL/SERVICE_-_Label) well, at the "Automatic Label SERVICE": *If an unbound variable in SELECT is named ?NAMELabel, then WDQS produces the label (rdfs:label) for the entity in variable ?NAME.*<br>
The ```WHERE``` describes what each non-label variable shall equal. Adding the ```OPTIONAL``` keyword makes the variable just supplementary, the query will still return a response if its not found.<br>
The ```?person ?label "%s"@en.``` gives the ?personLabel variable the name of the person. "%s" (like in C and C++) is a placeholder for a string, the string being ```person_name.replace('"', '\"')```, which basically just puts the name of the painter defined before, which is "Vincent van Gogh", and with the ```replace('"', '\"')``` functionality we put a "\" character before the quotation marks, to [escape these characters](https://en.wikipedia.org/wiki/Escape_sequence).<br> 
The ```?person wdt:P19 ?placeOfBirth.``` line and others tell which Wikidata item (entity) should the variable take as value. Here, it is a property, as represented by the "P", and P19 is the "place of birth" property of a profile. The "wdt" keyword stands for Wikidata "truthy", which basically points to a the properties-containing sub-URL. This substitutes the following SparQL code: ```PREFIX wdt: <http://www.wikidata.org/prop/direct/>```. For most common cases, this is used, or the general "wd" keyword for specific items. Here is an example for it:

  ```sparql

    query = '''
    SELECT ?painter ?painterLabel WHERE {
      ?painter wdt:P31 wd:Q5;          
              wdt:P106 wd:Q1028181.   
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }'''

  ```

This query is to find painters. The conditions are: those profiles, which have instance of property (P31) "human" (Q5) and occupation (P106) painter (Q1028181). 


### A more complex example
Let's try on something bigger, using artists from the [PainterPalette](https://github.com/me9hanics/PainterPalette) dataset:


```python
import pandas as pd
import numpy as np

artists_wikiart = pd.read_csv("https://raw.githubusercontent.com/me9hanics/PainterPalette/main/datasets/wikiart_artists.csv")
artists_wikiart["death_place"] = None #None for strings
artists_wikiart["death_year"] = np.nan #NaN for floats
artists_wikiart["locations"] = None #This is to not have warnings from pandas.
artists_wikiart["locations_with_years"] = None

examples = artists_wikiart[(artists_wikiart["artist"]=="Vincent van Gogh") | (artists_wikiart["artist"].str.contains("Rembrandt"))] #3 artists

for index, artist in examples["artist"].items():
    response = f.get_person_info(artist)
    if response is None:
        print(f"Could not find {artist}")
        continue

    examples.loc[index, "death_place"] = response.get("death_place")
    examples.loc[index, "death_year"] = f.find_year(response.get("death_date"))
    examples.loc[index, "locations"] = f.get_places_from_response(response)
    examples.loc[index, "locations_with_years"] = f.get_places_with_years_from_response(response)

    if examples.loc[index, "death_place"] is None:
        print(f"Could not find death place for {artist}")
    if examples.loc[index, "death_year"] is None:
        print(f"Could not find death year for {artist}")
    if examples.loc[index, "locations"] is None:
        print(f"Could not find locations for {artist}")
    if examples.loc[index, "locations_with_years"] is None:
        print(f"Could not find locations with years for {artist}")

examples.drop(columns=["pictures_count","styles"])
```




<div>

<table border="1" class="dataframe">
  <thead>
    <tr style="text-align: right;">
      <th></th>
      <th>artist</th>
      <th>movement</th>
      <th>styles_extended</th>
      <th>birth_place</th>
      <th>birth_year</th>
      <th>death_place</th>
      <th>death_year</th>
      <th>locations</th>
      <th>locations_with_years</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <th>997</th>
      <td>Rembrandt</td>
      <td>Baroque</td>
      <td>{Baroque:587},{Tenebrism:128},{Unknown:52}</td>
      <td>Leiden</td>
      <td>1606.0</td>
      <td>Amsterdam</td>
      <td>1669.0</td>
      <td>['Amsterdam', 'Leiden']</td>
      <td>['Amsterdam:1623-1625,1631-1669', 'Leiden:1625...</td>
    </tr>
    <tr>
      <th>1046</th>
      <td>Vincent van Gogh</td>
      <td>Post-Impressionism</td>
      <td>{Cloisonnism:11},{Impressionism:2},{Japonism:1...</td>
      <td>Zundert</td>
      <td>1853.0</td>
      <td>Breda</td>
      <td>1874.0</td>
      <td>['Saint-Rémy-de-Provence', 'The Hague', 'Ramsg...</td>
      <td>['Saint-Rémy-de-Provence:1889-1890', 'The Hagu...</td>
    </tr>
    <tr>
      <th>2461</th>
      <td>Rembrandt Peale</td>
      <td>Neoclassicism</td>
      <td>{Neoclassicism:85},{Romanticism:1},{Unknown:1}</td>
      <td>Pennsylvania</td>
      <td>1778.0</td>
      <td>Philadelphia</td>
      <td>1860.0</td>
      <td>['Boston', 'London', 'Baltimore', 'Washington,...</td>
      <td>[]</td>
    </tr>
  </tbody>
</table>
</div>


