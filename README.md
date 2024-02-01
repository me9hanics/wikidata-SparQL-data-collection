# sparql-wikidata-person-info-gathering
A notebook showing how one may use SparQL to gather various data of personalities (and other entities) from Wikidata.



## How to use

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
    name,period = place.replace(","," and ").split(":")
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
    

Now, on something bigger, using artists from the [PainterPalette](https://github.com/me9hanics/PainterPalette) dataset:


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


