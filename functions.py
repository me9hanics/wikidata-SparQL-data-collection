import requests
import time
import urllib3
import re

"""
Common inputs:

    person_name (str): Input (alias) name of the person.
    people (list of str): List of people's names.
    person_id (str): Wikidata ID of the person.
    retries (int): Maximum number of retries, in case of a status code error.
    delay0, delay1, delay2 (int): Delay times for retries.
    endpoint_url (str): the URL of the (SPARQL) endpoint, should be "https://query.wikidata.org/sparql".
    silent (bool): Whether to print out errors or not.

    placeofbirth, dateofbirth, dateofdeath, placeofdeath, worklocation, gender, citizenship, occupation (bool): Bools whether to include the attribute in the query.
    ..._return (bool): Same as above: Bools whether to return the attribute in the response.
"""

####################################### Basic functions #######################################

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


def sparql_query_by_dict(variable_names, WHERE_dict, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=10):
    #Example dict: {'painter': "wdt:P31 wd:Q5;", ... }
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


def create_person_info_from_results_with_id(person_id, person_results):
    #More information
    person_info = {
        'name': person_results[0].get('personLabel', {}).get('value', None),
        'id': person_id,
        'birth_place': None,
        'birth_date': None,
        'death_date': None,
        'death_place': None,
        'gender': None,
        'citizenship': None,
        'occupation': [],
        'work_locations': [],
        'exhibited_at': [],
        'influenced_by': [],
    }

    for result in person_results:
        if not person_info['name']:
            person_info['name'] = result.get('personLabel', {}).get('value', None)
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

        collection = result.get('collectionLabel', {}).get('value', None)
        if collection and collection not in person_info['exhibited_at']:
            person_info['exhibited_at'].append(collection)

        influence = result.get('influenceLabel', {}).get('value', None)
        if influence and influence not in person_info['influenced_by']:
            person_info['influenced_by'].append(influence)
    return person_info


def get_places_from_response(response, silent=True):
    places = []
    try:
        for place in response["work_locations"]:
            if place["location"] not in places:
                places.append(place["location"])
            elif not silent:
                print(f"{place['location']} already in list (person: {response['name']})")
    except KeyError:
        if not silent:
            print(f"Could not find work_locations in response for person: {response['name']}")
    return str(places)


def find_year(string):
    year = None
    if string is not None:
        year = re.findall(r"\d+(?=-)", string) #Until the first dash, match
        year = int(year[0]) if year != [] else None
    return year


def get_years_from_response_location(response_location, silent=True):
    years = []
    for key in ["start_time", "end_time", "point_in_time"]:
        try:
            year = find_year(response_location[key])
            if year is not None:
                years.append(year)
        except (KeyError, IndexError):
            if not silent:
                print(f"Could not find {key} or year in {key} for location: {response_location}")
    return years


def stringlist_to_list(stringlist):
    import ast #library not used for other cases, not worth importing generally
    return ast.literal_eval(stringlist) #but this functionality is already included in it


####################################### Queries for multiple instances (people) #######################################

def get_multiple_people_all_info_separate_responses(people, retries=3, delay=60):
    """
    NOTE: Only use this if you want to handle the responses separately.
    Otherwise, consider using 'get_multiple_people_all_info_fast_retry_missing' or 'get_multiple_people_all_info'.

    Get all information about multiple people from Wikidata.

    Parameters:
    - people, retries, delay: See at the top of the file.

    Returns:
    - list: List of responses (dictionaries) for each person.
    """
    #First, reduce the number of people in one query
    chunks = [people[i:i + 150] for i in range(0, len(people), 150)]
    responses = []
    for chunk in chunks:
        people_string = ' '.join(f'"{p}"' for p in chunk)
        query = f'''
        SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {{
          VALUES ?personLabel {{ {people_string} }}
          ?person ?label ?personLabel.
          ?person wdt:P31 wd:Q5.  #Ensure it's an instance of human, could happen that it's a statue of the person or something
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
    """
    NOTE: Querying multiple people at once is faster than querying them separately, however might miss some instances.
    Definitely consider using 'get_multiple_people_all_info_fast_retry_missing' which runs this function and tries again for missing instances.

    Get all information about multiple people from Wikidata, in one query per chunk (150 instances).

    Parameters:
    - people, retries, delay: See at the top of the file.

    Returns:
    - list: List of dictionaries for each person.
    """
    #Reduce the number of people in one query, one query per chunk
    chunks = [people[i:i + 150] for i in range(0, len(people), 150)]
    all_people_info = []
    for chunk in chunks:
        people_string = ' '.join(f'"{p}"' for p in chunk)
        query = f'''
        SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {{
          VALUES ?personLabel {{ {people_string} }}
          ?person ?label ?personLabel.
          ?person wdt:P31 wd:Q5.  #Ensure it's an instance of human, could happen that it's a statue of the person or something
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


def get_multiple_people_all_info_fast_retry_missing(people, retries=3, delay=60):
    gathered_people_fast = get_multiple_people_all_info(people, retries, delay)
    collected_names = [gathered_people_fast[k]['name'] for k in range(len(gathered_people_fast))]
    missing_people = [p for p in people if p not in collected_names]

    gathered_people_slow = []
    for person in missing_people:
        person_info = get_all_person_info(person)
        if person_info:
            gathered_people_slow.append(person_info)

    return gathered_people_fast + gathered_people_slow


def get_multiple_people_all_info_by_id(people_ids, retries=3, delay=60):
    # First, reduce the number of people in one query
    chunks = [people_ids[i:i + 150] for i in range(0, len(people_ids), 150)]
    all_people_info = []
    for chunk in chunks:
        people_id_string = ' '.join(f'wd:{id}' for id in chunk)
        query = f'''
        SELECT ?person ?personLabel ?name ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {{
          VALUES ?person {{ {people_id_string} }}
          ?person wdt:P31 wd:Q5.  #Ensure it's an instance of human, could happen that it's a statue of the person or something
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
          OPTIONAL {{ ?person rdfs:label ?name. FILTER(LANG(?name) = "en") }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        '''
        response_json = sparql_query(query, retries, delay)
        results = response_json.get('results', {}).get('bindings', [])
        for person_id in chunk:
            person_results = [r for r in results if r.get('person', {}).get('value').split('/')[-1] == person_id]
            if person_results:
                person_info = create_person_info_from_results_with_id(person_id, person_results)
                all_people_info.append(person_info)
    return all_people_info


def get_multiple_people_all_info_by_id_fast_retry_missing(people_ids, retries=3, delay=60):
    gathered_people_fastly = get_multiple_people_all_info_by_id(people_ids, retries, delay)
    collected_ids = [gathered_people_fastly[k]['id'] for k in range(len(gathered_people_fastly))]
    missing_people_ids = [id for id in people_ids if id not in collected_ids]

    gathered_people_slowly = []
    for person_id in missing_people_ids:
        person_info = get_all_person_info_by_id(person_id)
        if person_info:
            gathered_people_slowly.append(person_info)

    return gathered_people_fastly + gathered_people_slowly


####################################### Queries for 1 person #######################################
#(SPARQL query)

def get_all_person_info(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60):
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
                
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_all_person_info_improved(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    """
    An improved version of get_all_person_info.

    Basically, same as get_all_person_info but restricts to just human instances
    and gets the ID of the person too, only if it starts with Q.

    Would be for every language, but that also excludes person alias cases.

    Parameters:
    person_name: str
    endpoint_url: str
    retries: int
    delay0: int
    delay1: int
    delay2: int
    silent: bool

    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
    
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfBirthLabel ?dateOfDeath ?dateOfDeathLabel ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P31 wd:Q5.
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
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    ''' % person_name.replace('"', '\"') #For the "%s"@en part, the person_name is put in there, but for quotation marks, they are escaped with a backslash (regex-like)

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                ids = [result['person']['value'].split('/')[-1] for result in results]
                acceptable_ids = [i for i in ids if re.match(r'^Q\d+$', i)]

                if acceptable_ids:
                    person_info = create_person_info_from_results(person_name, results)

                    id_counts = {i: ids.count(i) for i in acceptable_ids}
                    most_common_id = max(id_counts, key=id_counts.get)
                    if id_counts[ids[0]] == max(id_counts.values()):
                        person_info['id'] = ids[0]
                    else:
                        person_info['id'] = most_common_id
                    return person_info
                else:
                    if not silent:
                        print(f"{person_name} has no valid ID.")
                    
                    return None
        
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            if not silent:
                print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_person_all_info_different_languages(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    #Change in the query: language can be anything. Drawback: doesn't detect aliases
    """
    Same as get_all_person_info_improved, but searching in all languages.
    The drawback is that that person_name string must match the name in the database, so aliases are not detected.
    
    Parameters:
    person_name: str
    endpoint_url: str
    retries: int
    delay0: int
    delay1: int
    delay2: int
    silent: bool
    
    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise
    """
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfBirthLabel ?dateOfDeath ?dateOfDeathLabel ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
        ?person ?label "%s".
        ?person wdt:P31 wd:Q5.
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
        SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],*". }
    }
    ''' % person_name.replace('"', '\"')

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                ids = [result['person']['value'].split('/')[-1] for result in results]
                acceptable_ids = [i for i in ids if re.match(r'^Q\d+$', i)]

                if acceptable_ids:
                    person_info = create_person_info_from_results(person_name, results)

                    id_counts = {i: ids.count(i) for i in acceptable_ids}
                    most_common_id = max(id_counts, key=id_counts.get)
                    if id_counts[ids[0]] == max(id_counts.values()):
                        person_info['id'] = ids[0]
                    else:
                        person_info['id'] = most_common_id
                    return person_info
                else:
                    if not silent:
                        print(f"{person_name} has no valid ID.")
                    
                    return None
        
            break #Don't need to try again, we have the data
        else: #Some status codes are handled
            if not silent:
                print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_person_info_retry_after(person_name, placeofbirth_return = True, dateofbirth_return = True, dateofdeath_return = True, placeofdeath_return = True, worklocation_return=True, gender_return=True, citizenship_return=True, occupation_return=True, endpoint_url="https://query.wikidata.org/sparql", retries=3):
    """
    Given what attributes to collect, get all of them from Wikidata about a person, with retry-after handling.
    
    Parameters:
    - person_name, *_return, endpoint_url, retries: See at the top of the file.

    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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
    """
    Not recommended, using get_all_person_info_improved or get_person_info_retry_after is more effective.

    Get all information about a person from Wikidata.

    Parameters:
    - person_name, endpoint_url, retries, delay: See at the top of the file.

    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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


def get_person_wikidata_name(person_name, retries = 3, delay = 1):
    """
    NOTE: If you query a person who has an English Wikipedia page, consider using get_person_wikidata_name_fast.
    Deprecated unless you need to search in all languages.

    Get the Wikidata database name of a person by their (alias) name.

    Parameters:
    - person_name, retries, delay: See at the top of the file.

    Returns:
    - str or None: Wikidata name of the person if successful, None otherwise.
    """
    query = '''
    SELECT ?person ?personLabel WHERE{
    ?person ?label "%s".
    ?person wdt:P31 wd:Q5.
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],*". }
    }
    '''% person_name.replace('"', '\"')
    # ?person wdt:P31 wd:Q5. : Ensure it's an instance of human, could happen that it's a statue of the person or something

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


def get_person_wikidata_name_fast(person_name, retries = 3, delay0 = 1,delay1=20, delay2 = 60):
    """
    Get the Wikidata database name of a person by their (alias) name.

    Parameters:
    - person_name, retries, delay0, delay1, delay2: See at the top of the file.

    Returns:
    - str or None: Wikidata name of the person if successful, None otherwise.
    """
    query = '''
    SELECT ?person ?personLabel WHERE{
    ?person ?label "%s"@en.
    ?person wdt:P31 wd:Q5.
    SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    '''% person_name.replace('"', '\"')
    # ?person wdt:P31 wd:Q5. : Ensure it's an instance of human, could happen that it's a statue of the person or something

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
            else:
                return None
        elif response.status_code in [408, 429, 500, 502, 503, 504]:
            
            if attempt == 0:
                time.sleep(delay0)
            elif attempt == 1:
                time.sleep(delay1)
            elif attempt == 2:
                time.sleep(delay2)
            
        elif response.status_code in [400, 404]:
            print("Error: %s"%response.status_code, "person name: ", person_name)
            return None
    return None


def get_person_aliases(person_name):
    #TODO
    #both aliases - and different language names
    pass


######## Location querying ########
#Exhibitions: See below, at Wikidata ID queries
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


######## Queries with or by Wikidata ID ########
def get_person_wikidata_id(person_name, retries = 3, delay0 = 1, delay1=20, delay2=60):
    """
    Get the Wikidata ID of a person by their name.
    
    Parameters:
    - person_name, retries, delay0, delay1, delay2: See at the top of the file.
    
    Returns:
    - str or None: Wikidata ID (starting with a Q) of the person if successful, None otherwise"""
    query = '''
    SELECT ?person ?personLabel WHERE{
    ?person ?label "%s".
    ?person wdt:P31 wd:Q5.  #Ensure it's an instance of human, could happen that it's a statue of the person or something
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],*". }
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
                        wikidata_id = person.split('/')[-1] # Extract Wikidata ID from URL
                        return wikidata_id
        elif response.status_code in [408, 429, 500, 502, 503, 504]:
            if attempt == 0:
                time.sleep(delay0)
            elif attempt == 1:
                time.sleep(delay1)
            elif attempt == 2:
                time.sleep(delay2)
        elif response.status_code in [400, 404]:
            print("Error: %s"%response.status_code)
            return None
    return None


def get_all_person_info_and_id(person_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    query = '''
    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime ?genderLabel ?citizenshipLabel ?occupationLabel WHERE {
      ?person ?label "%s"@en.
      ?person wdt:P31 wd:Q5.
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
            if results: 
                person_info = create_person_info_from_results(person_name, results)
                ids= [result['person']['value'].split('/')[-1] for result in results]
                acceptable_ids = [i for i in ids if re.match(r'^Q\d+$', i)]
                if acceptable_ids:
                    id_counts = {i: ids.count(i) for i in acceptable_ids}
                    most_common_id = max(id_counts, key=id_counts.get)
                    if id_counts[ids[0]] == max(id_counts.values()):
                        person_info['id'] = ids[0]
                    else:
                        person_info['id'] = most_common_id
                else:
                    if not silent:
                        print(f"{person_name} has an invalid ID: {person_info['id']} (is not in the form Q12345..)")
                    person_info['id'] = None
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            if not silent:
                print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_all_person_info_by_id(person_id, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    
    query = '''

    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?genderLabel ?countryCitizenshipLabel ?occupationLabel ?workLocationLabel ?exhibitionLabel ?collectionLabel ?influenceLabel WHERE {
      BIND(wd:%s AS ?person)
      OPTIONAL { ?person wdt:P19 ?placeOfBirth. }
      OPTIONAL { ?person wdt:P569 ?dateOfBirth. }
      OPTIONAL { ?person wdt:P570 ?dateOfDeath. }
      OPTIONAL { ?person wdt:P20 ?placeOfDeath. }
      OPTIONAL { ?person wdt:P21 ?gender. }
      OPTIONAL { ?person wdt:P27 ?countryCitizenship. }
      OPTIONAL { ?person wdt:P106 ?occupation. }
      OPTIONAL {
        ?person p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      #OPTIONAL { ?person wdt:P6379 ?collection. } #We comment this out now. For some artists (e.g. Rubens), it's too slow
      OPTIONAL { ?person wdt:P737 ?influence. }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". ?person rdfs:label ?personLabel. ?placeOfBirth rdfs:label ?placeOfBirthLabel. ?placeOfDeath rdfs:label ?placeOfDeathLabel. ?gender rdfs:label ?genderLabel. ?countryCitizenship rdfs:label ?countryCitizenshipLabel. ?occupation rdfs:label ?occupationLabel. ?workLocation rdfs:label ?workLocationLabel. ?collection rdfs:label ?collectionLabel. ?influence rdfs:label ?influenceLabel. }
    }
    
    '''% person_id

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                person_info = create_person_info_from_results_with_id(person_id, results)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            if not silent:
                print(f"Error fetching data for {person_id}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_exhibitions_by_id(person_id, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    query = '''
    SELECT ?person ?personLabel ?collectionLabel WHERE {
      BIND(wd:%s AS ?person)
      OPTIONAL { ?person wdt:P6379 ?collection. }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". ?person rdfs:label ?personLabel. ?collection rdfs:label ?collectionLabel. }
    }
    ''' % person_id

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            print('Results 0:', results[0])
            if results:
                collections = [result.get('collectionLabel', {}).get('value', None) for result in results if 'collectionLabel' in result]
                return collections
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            if not silent:
                print(f"Error fetching data for {person_id}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None


def get_all_person_info_and_exhibitions_by_id(person_id, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay0=1, delay1=20, delay2=60, silent = True):
    #This may be too slow for some artists, e.g. Rubens, therefore we get an error (query 1 minute timeout)
    query = '''

    SELECT ?person ?personLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?genderLabel ?countryCitizenshipLabel ?occupationLabel ?workLocationLabel ?exhibitionLabel ?collectionLabel ?influenceLabel WHERE {
      BIND(wd:%s AS ?person)
      OPTIONAL { ?person wdt:P19 ?placeOfBirth. }
      OPTIONAL { ?person wdt:P569 ?dateOfBirth. }
      OPTIONAL { ?person wdt:P570 ?dateOfDeath. }
      OPTIONAL { ?person wdt:P20 ?placeOfDeath. }
      OPTIONAL { ?person wdt:P21 ?gender. }
      OPTIONAL { ?person wdt:P27 ?countryCitizenship. }
      OPTIONAL { ?person wdt:P106 ?occupation. }
      OPTIONAL {
        ?person p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      OPTIONAL { ?person wdt:P6379 ?collection. }
      OPTIONAL { ?person wdt:P737 ?influence. }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". ?person rdfs:label ?personLabel. ?placeOfBirth rdfs:label ?placeOfBirthLabel. ?placeOfDeath rdfs:label ?placeOfDeathLabel. ?gender rdfs:label ?genderLabel. ?countryCitizenship rdfs:label ?countryCitizenshipLabel. ?occupation rdfs:label ?occupationLabel. ?workLocation rdfs:label ?workLocationLabel. ?collection rdfs:label ?collectionLabel. ?influence rdfs:label ?influenceLabel. }
    }
    
    '''% person_id

    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if not silent:
                print('Results 0:', results[0])
            if results:
                person_info = create_person_info_from_results_with_id(person_id, results)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            if not silent:
                print(f"Error fetching data for {person_id}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                if not silent:
                    print(f"Attempt {attempt + 1} of {retries}.")
                if attempt == 0:
                    time.sleep(delay0)
                elif attempt == 1:
                    time.sleep(delay1)
                elif attempt == 2:
                    time.sleep(delay2)
            else:
                break

    return None

