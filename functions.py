import requests
import time
import urllib3
import re

def sparql_query(query,  retries=3, delay=10):
    endpoint_url="https://query.wikidata.org/sparql"
    for attempt in range(retries):
        try:
            response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        except urllib3.exceptions.ProtocolError as e:
            print("Likely what happened: ProtocolError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
            print("Probably too big query, try using the chunked query function instead")
            break

        if response.status_code == 200: #Successful
            return response.json()
        else: #Some status codes could be handled handled, it's fine now to only handle time based status codes
            print(f"Error fetching data, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delay)
            else:
                print(f"Not retrying status code {response.status_code}.")
                break

    return None


#Example dict: {'painter': "wdt:P31 wd:Q5;", ... }
def sparql_query_by_dict(variable_names, WHERE_dict, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=10):
    select = "SELECT " + " ".join([f"?{name}" for name in variable_names])
    where = " WHERE {\n"
    for variable, value in WHERE_dict.items():
        where += f"?{variable} {value}\n"
    service = '\nSERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }' #Need to watch out for quotation marks
    
    query = select + where + service
    return sparql_query(query, retries, delay)


def sparql_query_retry_after(query,  retries=3):

    endpoint_url="https://query.wikidata.org/sparql"
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            return response.json()
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                delay = 1
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        delay = int(retry_after)
                time.sleep(delay)
            else:
                print(f"Not retrying status code {response.status_code}.")
                break

    return None


def get_query_from_input(person, placeofbirth = True, dateofbirth = True, dateofdeath = True, placeofdeath = True, worklocation=True, gender=True, citizenship=True, occupation=True):
    query = "SELECT ?person ?personLabel"
    if placeofbirth:
        query += " ?placeOfBirthLabel"
    if dateofbirth:
        query += " ?dateOfBirth"
    if dateofdeath:
        query += " ?dateOfDeath"
    if placeofdeath:
        query += " ?placeOfDeathLabel"
    if gender:
        query += " ?genderLabel"
    if citizenship:
        query += " ?citizenshipLabel"
    if occupation:
        query += " ?occupationLabel"
    if worklocation: #Optional, need to be handled differently
        query += " ?workLocationLabel ?startTime ?endTime ?pointInTime"

    query += " WHERE {\n"
    query += f'?person ?label "{person}"@en.\n'
    if placeofbirth:
        query += "OPTIONAL {?person wdt:P19 ?placeOfBirth. }\n"
    if dateofbirth:
        query += "OPTIONAL {?person wdt:P569 ?dateOfBirth. }\n"
    if dateofdeath:
        query += "OPTIONAL {?person wdt:P570 ?dateOfDeath. }\n"
    if placeofdeath:
        query += "OPTIONAL {?person wdt:P20 ?placeOfDeath. }\n"
    if gender:
        query += "OPTIONAL { ?person wdt:P21 ?gender. }\n"
    if citizenship:
        query += "OPTIONAL { ?person wdt:P27 ?citizenship. }\n"
    if occupation:
        query += "OPTIONAL { ?person wdt:P106 ?occupation. }\n"
    if worklocation:
        query += "OPTIONAL {\n?person p:P937 ?workStmt.\n?workStmt ps:P937 ?workLocation.\nOPTIONAL { ?workStmt pq:P580 ?startTime. }\nOPTIONAL { ?workStmt pq:P582 ?endTime. }\nOPTIONAL { ?workStmt pq:P585 ?pointInTime. }\n}\n"
    query += "SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". }\n}"
    return query


def create_person_info_from_results(person_name, person_results):
    person_info = {
        'name': person_name,
        'birth_place': None,
        'birth_date': None,
        'death_date': None,
        'death_place': None,
        'gender': None,
        'citizenship': None,
        'occupation': [],
        'work_locations': [],
    }
    for result in person_results:
        if not person_info['birth_place']:
            person_info['birth_place'] = result.get('placeOfBirthLabel', {}).get('value', None)
        if not person_info['birth_date']:
            person_info['birth_date'] = result.get('dateOfBirth', {}).get('value', None)
        if not person_info['death_date']:
            person_info['death_date'] = result.get('dateOfDeath', {}).get('value', None)
        if not person_info['death_place']:
            person_info['death_place'] = result.get('placeOfDeathLabel', {}).get('value', None)
        if not person_info['gender']:
            person_info['gender'] = result.get('genderLabel', {}).get('value', None)
        if not person_info['citizenship']:
            person_info['citizenship'] = result.get('citizenshipLabel', {}).get('value', None)

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


def get_all_person_info(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):

    #SPARQL query
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
      ?person ?label "%s"@en.
      OPTIONAL {?person wdt:P19 ?placeOfBirth. }
      OPTIONAL {?person wdt:P569 ?dateOfBirth. }
      OPTIONAL {?person wdt:P570 ?dateOfDeath. }
      OPTIONAL {?person wdt:P20 ?placeOfDeath. }
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
            if results: #We could just use create_person_info_from_results here, but I keep the current code to not break anything
                person_info = {
                    'name': person_name,
                    'birth_place': None,
                    'birth_date': None,
                    'death_date': None,
                    'death_place': None,
                    'gender': None,
                    'citizenship': None,
                    'occupation': [],
                    'work_locations': [],
                }
                for result in results:
                    if not person_info['birth_place']:
                        person_info['birth_place'] = result.get('placeOfBirthLabel', {}).get('value', None)
                    if not person_info['birth_date']:
                        person_info['birth_date'] = result.get('dateOfBirth', {}).get('value', None)
                    if not person_info['death_date']:
                        person_info['death_date'] = result.get('dateOfDeath', {}).get('value', None)
                    if not person_info['death_place']:
                        person_info['death_place'] = result.get('placeOfDeathLabel', {}).get('value', None)
                    if not person_info['gender']:
                        person_info['gender'] = result.get('genderLabel', {}).get('value', None)
                    if not person_info['citizenship']:
                        person_info['citizenship'] = result.get('citizenshipLabel', {}).get('value', None)
            
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
            print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delay)
            else:
                break

    return None


def get_person_wikidata_name(person_name, retries = 3, delay = 1):
    query = '''
    SELECT ?person ?personLabel WHERE{
    ?person ?label "%s"@en.
    
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    '''% person_name.replace('"', '\"')

    for attempt in range(retries):
        response = requests.get("https://query.wikidata.org/sparql", params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                for result in results:
                    person = result.get('person', {}).get('value', None)
                    label = result.get('personLabel', {}).get('value', None)
                    if person and 'entity/Q' in person and label: #We get a ton of results, and almost all of them a gibberish, so we need to filter them
                        return label
        elif response.status_code in [408, 429, 500, 502, 503, 504]:
            time.sleep(delay)
        elif response.status_code in [400, 404]:
            print("Error: %s"%response.status_code)
            return None
    return None


def get_person_aliases(person_name):
    #TODO
    #both aliases - and different language names
    pass


def get_all_person_info_by_id(person_id, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    #SPARQL query
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
      BIND(wd:%s AS ?person).
      OPTIONAL {?person wdt:P19 ?placeOfBirth. }
      OPTIONAL {?person wdt:P569 ?dateOfBirth. }
      OPTIONAL {?person wdt:P570 ?dateOfDeath. }
      OPTIONAL {?person wdt:P20 ?placeOfDeath. }
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
    ''' % person_id

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_name = results[0].get('personLabel', {}).get('value', None)
                person_info = create_person_info_from_results(person_name, results)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {person_id}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delay)
            else:
                break

    return None


def get_multiple_people_all_info_separate_responses(people, retries=3, delay=60):
    #First, reduce the number of people in one query
    chunks = [people[i:i + 150] for i in range(0, len(people), 150)]
    responses = []
    for chunk in chunks:
        people_string = ' '.join(f'"{p}"' for p in chunk)
        query = f'''
        SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {{
          VALUES ?personLabel {{ {people_string} }}
          ?person ?label ?personLabel.
          ?person wdt:P19 ?placeOfBirth.
          ?person wdt:P569 ?dateOfBirth.
          ?person wdt:P570 ?dateOfDeath.
          ?person wdt:P20 ?placeOfDeath.
          OPTIONAL {{ ?person wdt:P21 ?gender. }}
          OPTIONAL {{ ?person wdt:P27 ?citizenship. }}
          OPTIONAL {{ ?person wdt:P106 ?occupation. }}
          OPTIONAL {{
            ?person p:P937 ?workStmt.
            ?workStmt ps:P937 ?workLocation.
            OPTIONAL {{ ?workStmt pq:P580 ?startTime. }}
            OPTIONAL {{ ?workStmt pq:P582 ?endTime. }}
            OPTIONAL {{ ?workStmt pq:P585 ?pointInTime. }}
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        '''
        response_json = sparql_query(query, retries, delay)
        responses.append(response_json)
    return responses


def get_multiple_people_all_info(people, retries=3, delay=60):
    # First, reduce the number of people in one query
    chunks = [people[i:i + 150] for i in range(0, len(people), 150)]
    all_people_info = []
    for chunk in chunks:
        people_string = ' '.join(f'"{p}"' for p in chunk)
        query = f'''
        SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {{
          VALUES ?personLabel {{ {people_string} }}
          ?person ?label ?personLabel.
          ?person wdt:P19 ?placeOfBirth.
          ?person wdt:P569 ?dateOfBirth.
          ?person wdt:P570 ?dateOfDeath.
          ?person wdt:P20 ?placeOfDeath.
          OPTIONAL {{ ?person wdt:P21 ?gender. }}
          OPTIONAL {{ ?person wdt:P27 ?citizenship. }}
          OPTIONAL {{ ?person wdt:P106 ?occupation. }}
          OPTIONAL {{
            ?person p:P937 ?workStmt.
            ?workStmt ps:P937 ?workLocation.
            OPTIONAL {{ ?workStmt pq:P580 ?startTime. }}
            OPTIONAL {{ ?workStmt pq:P582 ?endTime. }}
            OPTIONAL {{ ?workStmt pq:P585 ?pointInTime. }}
          }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        '''
        response_json = sparql_query(query, retries, delay)
        results = response_json.get('results', {}).get('bindings', [])
        for person_name in chunk:
            person_results = [r for r in results if r.get('personLabel', {}).get('value') == person_name]
            if person_results:
                person_info = create_person_info_from_results(person_name, person_results)
                all_people_info.append(person_info)
    return all_people_info


def get_person_info_retry_after(person_name, placeofbirth_return = True, dateofbirth_return = True, dateofdeath_return = True, placeofdeath_return = True, worklocation_return=True, gender_return=True, citizenship_return=True, occupation_return=True, endpoint_url="https://query.wikidata.org/sparql", retries=3):
    query = get_query_from_input(person_name, placeofbirth_return, dateofbirth_return, dateofdeath_return, placeofdeath_return, worklocation_return, gender_return, citizenship_return, occupation_return)
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})

        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_info = {
                    'name': person_name,
                    'birth_place': None,
                    'birth_date': None,
                    'death_date': None,
                    'death_place': None,
                    'gender': None,
                    'citizenship': None,
                    'occupation': [],
                    'work_locations': []
                }

                for result in results:
                    if placeofbirth_return and not person_info['birth_place']:
                        person_info['birth_place'] = result.get('placeOfBirthLabel', {}).get('value', None)
                    if dateofbirth_return and not person_info['birth_date']:
                        person_info['birth_date'] = result.get('dateOfBirth', {}).get('value', None)
                    if dateofdeath_return and not person_info['death_date']:
                        person_info['death_date'] = result.get('dateOfDeath', {}).get('value', None)
                    if placeofdeath_return and not person_info['death_place']:
                        person_info['death_place'] = result.get('placeOfDeathLabel', {}).get('value', None)
                    if gender_return and not person_info['gender']:
                        person_info['gender'] = result.get('genderLabel', {}).get('value', None)
                    if citizenship_return and not person_info['citizenship']:
                        person_info['citizenship'] = result.get('citizenshipLabel', {}).get('value', None)
                    if occupation_return:
                        occupation = result.get('occupationLabel', {}).get('value', None)
                        if occupation and occupation not in person_info['occupation']:
                            person_info['occupation'].append(occupation)
                    if worklocation_return:
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
            print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                delay = 60
                if response.status_code == 429:
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        delay = int(retry_after)
                time.sleep(delay)
            else:
                break

    return None


def get_person_info(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
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
            print(f"Error fetching data for {person_name}, status code: {response.status_code}")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delay)
            else:
                break

    return None


def get_person_locations(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
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
            print(f"Error fetching data for {person_name}, status code: {response.status_code}")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
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
    year = None
    if string is not None:
        year = re.findall(r"\d+(?=-)", string) #Until the first dash, match
        year = int(year[0]) if year != [] else None
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
