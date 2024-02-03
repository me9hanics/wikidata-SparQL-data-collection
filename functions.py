def sparql_query(query,  retries=3, delay=10):
    import requests
    import time

    endpoint_url="https://query.wikidata.org/sparql"
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            return response.json()
        else: #Some status codes could be handled handled, it's fine now to only handle time based status codes
            print(f"Error fetching data, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None


#Example dict: {'painter': "wdt:P31 wd:Q5;", }
def sparql_query_by_dict(variable_names, WHERE_dict, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    from functions import sparql_query
    select = "SELECT " + " ".join([f"?{name}" for name in variable_names])
    where = " WHERE {\n"
    for variable, value in WHERE_dict.items():
        where += f"?{variable} {value}\n"
    service = '\nSERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }' #Need to watch out for quotation marks
    
    query = select + where + service
    return sparql_query(query, retries, delay)


def get_all_person_info(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    import requests
    import time

    #SPARQL query
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P19 ?placeOfBirth.
      ?person wdt:P569 ?dateOfBirth.
      ?person wdt:P570 ?dateOfDeath.
      ?person wdt:P20 ?placeOfDeath.
      OPTIONAL { ?person wdt:P21 ?gender. }
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
    ''' % person_name.replace('"', '\"') #For the "%s"@en part, the person_name is put in there, but for quotation marks, they are escaped with a backslash (regex-like)

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_info = {
                    'name': person_name,
                    'birth_place': results[0].get('placeOfBirthLabel', {}).get('value', None),
                    'birth_date': results[0].get('dateOfBirth', {}).get('value', None),
                    'death_date': results[0].get('dateOfDeath', {}).get('value', None),
                    'death_place': results[0].get('placeOfDeathLabel', {}).get('value', None),
                    'gender': results[0].get('genderLabel', {}).get('value', None),
                    'citizenship': results[0].get('citizenshipLabel', {}).get('value', None),
                    'occupation': [],
                    'work_locations': [],
                }
                for result in results:
                    occupation = result.get('occupationLabel', {}).get('value', None)
                    if occupation and occupation not in person_info['occupation']:
                        person_info['occupation'].append(occupation)
                    
                    work_location = result.get('workLocationLabel', {}).get('value', None)
                    if work_location:
                        location_info = {
                            'location': work_location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        }
                        if location_info not in person_info['work_locations']:
                            person_info['work_locations'].append(location_info)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {person_name}, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None


def get_person_info(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    import requests
    import time

    #SPARQL query
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P19 ?placeOfBirth.
      ?person wdt:P569 ?dateOfBirth.
      ?person wdt:P570 ?dateOfDeath.
      ?person wdt:P20 ?placeOfDeath.
      OPTIONAL {
        ?person p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ''' % person_name.replace('"', '\"') #For the "%s"@en part, the person_name is put in there, but for quotation marks, they are escaped with a backslash (regex-like)

    #Attempts till we get a response / 'retries' goes over the limit
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_info = {
                    'name': person_name,
                    'birth_place': results[0].get('placeOfBirthLabel', {}).get('value', None),
                    'birth_date': results[0].get('dateOfBirth', {}).get('value', None),
                    'death_date': results[0].get('dateOfDeath', {}).get('value', None),
                    'death_place': results[0].get('placeOfDeathLabel', {}).get('value', None),
                    'work_locations': [],
                }
                for result in results:
                    work_location = result.get('workLocationLabel', {}).get('value', None)
                    if work_location:
                        location_info = {
                            'location': work_location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        }
                        if location_info not in person_info['work_locations']:
                            person_info['work_locations'].append(location_info)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {person_name}, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None


def get_person_locations(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    import requests
    import time

    #SPARQL query
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P19 ?placeOfBirth.
      ?person wdt:P20 ?placeOfDeath.
      OPTIONAL {
        ?person p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ''' % person_name.replace('"', '\"') #For the "%s"@en part, the person_name is put in there, but for quotation marks, they are escaped with a backslash (regex-like)
    #We already have birth data, so this function will not be used

    #Attempts till we get a response / 'retries' goes over the limit
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_info = {
                    'name': person_name,
                    'birth_place': results[0].get('placeOfBirthLabel', {}).get('value', None),
                    'death_place': results[0].get('placeOfDeathLabel', {}).get('value', None),
                    'work_locations': [],
                }
                for result in results:
                    work_location = result.get('workLocationLabel', {}).get('value', None)
                    if work_location:
                        location_info = {
                            'location': work_location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        }
                        if location_info not in person_info['work_locations']:
                            person_info['work_locations'].append(location_info)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {person_name}, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None


def get_places_from_response(response, quiet=True):
    places = []
    try:
        for place in response["work_locations"]:
            if place["location"] not in places:
                places.append(place["location"])
            elif not quiet:
                print(f"{place['location']} already in list (person: {response['name']})")
    except KeyError:
        if not quiet:
            print(f"Could not find work_locations in response for person: {response['name']}")
    return str(places)


def find_year(string):
    import re
    year = None
    if string is not None:
        year = re.findall(r"\d+(?=-)", string) #Until the first dash, match
        if year != []:
            year = int(year[0])
    return year


def get_years_from_response_location(response_location, quiet=True):
    years = []
    for key in ["start_time", "end_time", "point_in_time"]:
        try:
            year = find_year(response_location[key])
            if year is not None:
                years.append(year)
        except (KeyError, IndexError):
            if not quiet:
                print(f"Could not find {key} or year in {key} for location: {response_location}")
    return years


def get_places_with_years_from_response(response):
    places = []
    for place in response["work_locations"]:
        years = get_years_from_response_location(place)
        if years != []:
            min_year = min(years); max_year = max(years)
            #Checking if the location is already in the list
            if not any(p.split(':')[0] == place["location"] for p in places):#Just get the part before the colon, which is the location's name
                places.append(f"{place['location']}:{min_year}-{max_year}")
            else:
                #Find the index of the location in the places list
                for i, p in enumerate(places):
                    if p.split(':')[0] == place["location"]:
                        #Add these years next to the existing years
                        places[i] = f"{p},{min_year}-{max_year}"
                        break
    return str(places)


def stringlist_to_list(stringlist):
    import ast #hardly related library, but this functionality is already included in it
    return ast.literal_eval(stringlist)
