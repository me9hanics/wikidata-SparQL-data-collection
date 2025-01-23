import requests
import time
import urllib3
import re

"""
Module with functions to query Wikidata using the SPARQL API and process the results.
Particularly, functions to query information about (multiple) people, such as their birth dates, locations, etc.

There are NO! dependencies (other than the standard library) for this module, with
    the exception of the 'pandas' library if you intend to use the 'results_dataframe' function.
Created by: Mihaly Hanics, 2024

Common inputs:

    person_name (str): Input (alias) name of the person.
    people (list of str): List of people's names.
    person_id (str): Wikidata ID of the person.
    retries (int): Maximum number of retries, in case of a status code error.
    delay or delays (int|list of int): Delay time(s) for retries.
    silent (bool): Whether to print out errors or not.

    placeofbirth, dateofbirth, dateofdeath, placeofdeath, worklocation, gender, citizenship, occupation (bool): Bools whether to include the attribute in the query.
    ..._return (bool): Same as above: Bools whether to return the attribute in the response.
"""

####################################### Basic SparQL query functions #######################################

def sparql_query(query,  retries=3, delay=10, endpoint_url="https://query.wikidata.org/sparql"):
    """
    Make a SPARQL query API call to the Wikidata endpoint.

    Parameters:
    - query (str): The SPARQL query, provided as string. It will be used as the 'query' parameter in the URL.
        An example: query = ''' SELECT ?painter ?painterLabel WHERE {
                                    ?painter wdt:P31 wd:Q5;          
                                    wdt:P106 wd:Q1028181.   
                                    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
                                }'''
    - endpoint_url (str): the URL of the (SPARQL) endpoint, should be "https://query.wikidata.org/sparql" in all cases,
        unless you manually want to change it to another endpoint.
    - retries, delay: See at the top of the file.

    Returns:
    - dict or None: The JSON response of the query if successful, None otherwise.
    """
    if type(delay)==int:
        delay = [delay]*retries
    elif type(delay)!=list:
        raise ValueError("Delay should be an integer or a list of integers.")
    
    for attempt in range(retries):
        try:
            response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        except urllib3.exceptions.ProtocolError as e:
            print("Likely what happened: ProtocolError: ('Connection aborted.', RemoteDisconnected('Remote end closed connection without response'))")
            print("Probably too big query (typically happens when querying exhibitions for many artists), try using chunks in querying instead (e.g. get_multiple_people_all_info_retry_missing).")
            break

        if response.status_code == 200: #Successful
            return response.json()
        else: #Some status codes could be handled handled, it's fine now to only handle time based status codes
            print(f"Error fetching data, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delay[attempt])
            else:
                print(f"Not retrying status code {response.status_code}.")
                break
    return None


def sparql_query_by_dict(variable_names, WHERE_clause_matches, multiple_people_list = None, multiple_people_var_name = "person",
                         after_where="", label_language = False, label_language_param = "[AUTO_LANGUAGE],en" , run = True,
                         retries=3, delays=[1, 10, 60]):
    """
    Make a SPARQL query using a dictionary to construct the WHERE clause.

    Parameters:
    - variable_names (list of str): List of variable names to select.
    - WHERE_clause_matches (str|dict|NoneType): Dictionary where keys are variable names and values are conditions.
            Example: WHERE_clause_matches = {'?painter': "wdt:P31 wd:Q5;", '?person': "wdt:P106 ?occupation." ... }
    - multiple_people_list (list of str or None): If querying multiple people, list of names to query for. 
            If None, include the only person in the WHERE clause.
    - multiple_people_variable_name (str or None): If querying multiple people, the name of the variable corresponding to values.
            A typical example: if "person", the WHERE clause will start with "VALUES ?personLabel { {multiple_people_list} }", followed up with "?person ?label ?personLabel."
            Do not forget to include the corresponding SELECT variable in variable_names.
    - after_where (str): Extra part to add to the query, after the WHERE clause (except service for label language).
            Could be ordering, etc. Example: "ORDER BY ?dateOfBirth"
    - label_language (bool): Whether to include a service parameter with the language label.
            Often handy, but this service is only for label language.
    - label_language_param (str): The language label in the service parameter.
            Usually "[AUTO_LANGUAGE],en" or "en".
    - retries, delay: See at the top of the file.

    Returns:
    - dict or None: The JSON response of the query if successful, None otherwise.
    """
    if type(variable_names) != list:
        variable_names = [variable_names]
    if type(WHERE_clause_matches) == dict:
        print(WHERE_clause_matches)
        WHERE_clause_matches = '\n'.join([f"{variable} {value} ." for variable, value in WHERE_clause_matches.items()])
        print("\n",WHERE_clause_matches)
    if type(WHERE_clause_matches) == type(None):
        WHERE_clause_matches = ""

    select = "SELECT " + " ".join([f"?{name}" for name in variable_names])
    where = " WHERE {\n"

    if type(multiple_people_list) == list:
        """
        Something resembling this:
        VALUES ?personLabel { "Vincent van Gogh" "Pablo Picasso" }
        ?person ?label ?personLabel.
        """
        people_string = ' '.join(f'"{p}"' for p in multiple_people_list)
        where += f'VALUES ?{multiple_people_var_name}Label {{ {people_string} }}\n'
        where += f"?{multiple_people_var_name} ?label ?{multiple_people_var_name}Label.\n"

    where += WHERE_clause_matches + "\n"
    if label_language:
        where += '\nSERVICE wikibase:label { bd:serviceParam wikibase:language "' + label_language_param + '". }' #Watch out for quotation marks
    where += "\n}"
    
    extra = ''
    if after_where:
        extra += after_where

    query = select + where + extra
    if run:
        return sparql_query(query, retries, delays)
    return query


def construct_person_query(person, **kwargs):
    """
    Construct a SPARQL query based on the given parameters.

    Parameters:
    - person (str): The name of the person.
    - placeofbirth, dateofbirth, dateofdeath, placeofdeath, worklocation, gender, citizenship, occupation: See at the top of the file.

    Returns:
    - str: The constructed SPARQL query.
    """
    properties = {'placeofbirth':'P19','dateofbirth':'P569',
                  'dateofdeath':'P570','placeofdeath':'P20',
                  'gender':'P21','citizenship':'P27',
                  'occupation':'P106','worklocation':'P937'}
    
    query = "SELECT ?person ?personLabel"
    for property in properties.keys():
        if kwargs.get(property, False):
            keyword = property
            if property not in ['placeofbirth', 'placeofdeath',]:
                keyword += "Label"
            query += f" ?{keyword}"
            if property == "worklocation":
                query += " ?startTime ?endTime ?pointInTime"

    query += " WHERE {\n" + f'?person ?label "{person}"@en.\n'

    for property in properties.keys():
        if kwargs.get(property, False):
            if property == "worklocation":
                query += f"OPTIONAL {{ ?person p:{properties[property]} ?workStmt.\n?workStmt ps:{properties[property]} ?workLocation.\n \
                           OPTIONAL {{ ?workStmt pq:P580 ?startTime. }}\n \
                           OPTIONAL {{ ?workStmt pq:P582 ?endTime. }}\n \
                           OPTIONAL {{ ?workStmt pq:P585 ?pointInTime. }}\n}}\n"
            else:
                query += f"OPTIONAL {{ ?person wdt:{properties[property]} ?{property}. }}\n"
    query += "SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". }\n}"
    return query


def get_entity_label(entity_id, retries=3, lang="all", delays=[1, 10, 60], **kwargs):
    """
    Get the label of an entity from Wikidata (typically a person's name).
    
    Parameters:
    - entity_id (str): The Wikidata ID of the entity.
    - lang (str): The language of the label (in the response). Can be:
        - ISO 639-1 code (e.g. "en")
        - "all" for getting all language responses
        - "most" for selecting the most name among responses
        - "threshold" for selecting above threshold given by linear_thresholding.
    - retries, delays: See at the top of the file."""
    if type(entity_id) != str:
        try:
            entity_id = str(entity_id)
        except:
            raise ValueError("Invalid entity_id (type).")
    if not re.match(r'^Q\d+$', entity_id):
        if re.match(r'\d+$', entity_id):
            entity_id = "Q" + entity_id
        else:
            raise ValueError("Unknown entity_id format; try either Q1234.. or the number (1234..).")
        
    where = f'wd:{entity_id} rdfs:label ?label.'
    if not lang in ["all", "most", "threshold"]:
        where += f'FILTER(LANG(?label) = "{lang}").'
    response_json = sparql_query_by_dict(["label"], where, label_language=False,
                                         run=True, retries=retries, delays=delays)
    if response_json:
        results = response_json.get('results', {}).get('bindings', [])
        if results:
            if not lang in ["all", "most", "threshold"]:
                if len(results) > 1:
                    print(f"Multiple results for language {lang}; this is unexpected behaviour. \
                          Returning the first one.")
                return results[0].get('label', {}).get('value', None)
            else:
                labels = [result.get('label', {}).get('value', None) for result in results]
                labels = [i for i in labels if i is not None]
                if lang == "all":
                    return labels
                if lang == "most":
                    return max(set(labels), key=labels.count)
                if lang == "threshold":
                    return above_threshold_counts(["label"], results, **kwargs)
    return None

####################################### Utility functions #######################################

def linear_thresholding(high, low = 0, rate = 1/2.5, shift=0.5):
    """
    Return the 0-1 cutoff threshold from a linear regression function.
    Default argument values represent a model that accepts 1, when high = 1, but does not accept 2 when high = 4.
    The cutoff point is (high-low)*rate + low + shift. Typically, high is the maximum value, low is 0.

    Parameters:
    - high (int|float): Typically the maximum value.
    - low (int|float): Typically the minimum value.
    - rate (float): The rate of the linear function.
    - shift (float): The shift in x-axis.

    Returns:
    - float: The threshold value.
    """
    threshold = (high-low)*rate + low + shift
    return threshold


def key_value_counts(key, results):
    """
    Get the counts of each value for a key in SPARQL query results.

    Parameters:
    - key (str): The key to get the counts for.
    - results (list of dict): Results dict (from the SPARQL query).

    Returns:
    - dict: A dictionary with the counts of each value for the key.
    """
    values = [result.get(key, {}).get('value', None) for result in results]
    counts = {i: values.count(i) for i in values}
    return counts


def most_common_results(keys, results):
    """
    Get the most common values for a list of keys (from SPARQL query results).
    
    Parameters:
    - keys (list of str): The keys to get the most common values for.
    - results (list of dict): Results dict (from the SPARQL query).
    
    Returns:
    - list: The most common value for each key."""
    most_common_values = []
    if type(keys) != list:
        keys = [keys]
    for key in keys:
        counts = key_value_counts(key, results)
        most_common = max(counts, key=counts.get)
        most_common_values.append(most_common)

    if len(most_common_values) == 1:
        return most_common_values[0]
    return most_common_values
    

def above_threshold_counts(keys, results, threshold=0.4, baseline="max", **kwargs):
    """
    For each key, collect only the list of values that have above threshold counts.

    Parameters:
    - keys (list of str): The keys to get the most common values for.
    - results (list of dict): Results dict (from the SPARQL query).
    - threshold (int|float): Threshold for counts. If an integer, it's the minimum count,
        if a float, it's the minimum ratio. If it the string "linear", it's a linearly calculated threshold.
    - baseline (str): The baseline for a float (ratio) threshold. Can be "max" or "total".
    """
    acceptable_values = []
    if type(keys) != list:
        keys = [keys]
    for key in keys:
        counts = key_value_counts(key, results)
        if isinstance(threshold, int):
            acceptable_values.append([i for i in counts if counts[i] >= threshold])
        elif isinstance(threshold, float):
            if baseline == "max":
                high = max(counts.values())
            else: #baseline == "total"
                high = sum(counts.values())
            acceptable_values.append([i for i in counts if (counts[i] / high >= threshold) and i is not None])
        elif threshold == "linear":
            high = max(counts.values())
            acceptable_values.append([i for i in counts if (counts[i] >= linear_thresholding(high, **kwargs)) and i is not None])
        else:
            raise ValueError("Invalid threshold value.")
    
    if len(acceptable_values) == 1:
        return acceptable_values[0]
    return acceptable_values


def get_id_from_results(person_results):
    """
    Get the Wikidata ID from the SPARQL query results.

    Parameters:
    - results (list of dict): The results from the SPARQL query.

    Returns:
    - str or None: The Wikidata ID of the person if found, None otherwise.
    """
    if person_results:
        ids = [result.get('person', {}).get('value', "").split('/')[-1] for result in person_results]
        ids = [i for i in ids if re.match(r'^Q\d+$', i)]
        id_counts = {i: ids.count(i) for i in ids}
        most_common_id = max(id_counts, key=id_counts.get)
        return most_common_id
    return None


def create_person_info_from_results(person_name, person_results):
    """
    Create a dictionary with person information from SPARQL query results.

    Parameters:
    - person_name (str): The name of the person.
    - person_results (list of dict): Results dict (from the SPARQL query).

    Returns:
    - dict: A dictionary containing the person's information.
    """
    person_info = {
        'name': person_name,
        'birth_place': None,
        'birth_date': None,
        'death_date': None,
        'death_place': None,
        'gender': None,
        'citizenship': None,
        'locations': None,
        'occupation': None,
        'location_dates': [],
    }
    most_common_keys = most_common_results(['placeOfBirthLabel', 'dateOfBirth', 'dateOfDeath', 'placeOfDeathLabel',
                                            'genderLabel', 'citizenshipLabel'], person_results)
    person_info['birth_place'], person_info['birth_date'], person_info['death_date'] = most_common_keys[0], most_common_keys[1], most_common_keys[2]
    person_info['death_place'], person_info['gender'], person_info['citizenship'] = most_common_keys[3], most_common_keys[4], most_common_keys[5]
    person_info['occupation'] = ",".join(above_threshold_counts(['occupationLabel'], person_results, threshold="linear"))
    acceptable_locations = above_threshold_counts(['workLocationLabel'], person_results, threshold="linear", rate=1/4, shift=0.49)
    person_info['locations'] = ",".join(acceptable_locations)
    for result in person_results:
        work_location = result.get('workLocationLabel', {}).get('value', None)
        if work_location in acceptable_locations:
            location_info = {
                'location': work_location,
                'start_time': result.get('startTime', {}).get('value', None),
                'end_time': result.get('endTime', {}).get('value', None),
                'point_in_time': result.get('pointInTime', {}).get('value', None),
            }
            if location_info not in person_info['location_dates']:
                person_info['location_dates'].append(location_info)
    return person_info


def create_person_info_from_results_with_id(person_id, person_results):
    """
    Create a dictionary with person information from SPARQL query results, including the person's ID.

    Parameters:
    - person_id (str): The Wikidata ID of the person.
    - person_results (list of dict): The results from the SPARQL query.

    Returns:
    - dict: A dictionary containing the person's information.
    """
    #More information
    person_info = {
        'name': most_common_results(['personLabel'], person_results),
        'id': person_id,
    }
    person_info.update(create_person_info_from_results(person_info['name'], person_results))
    return person_info


def find_year(string):
    """
    Extract the year from a string.

    Parameters:
    - string (str): The string containing the year.

    Returns:
    - int or None: The extracted year or None if not found.
    """
    year = None
    if string is not None:
        year = re.findall(r"\d+(?=-)", string) #Until the first dash, match
        year = int(year[0]) if year != [] else None
    return year


def get_years_from_response_location(response_location, silent=True):
    """
    Extract years from a response location.

    Parameters:
    - response_location (dict): The response location dictionary.
    - silent (bool): Whether to print out errors or not.

    Returns:
    - list: A list of extracted years.
    """
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


def get_places_from_response(response, silent=True, return_type = "comma_separated_string"):
    """
    Extract work locations from the response.

    Parameters:
    - response (dict): The response dictionary containing person information.
    - silent (bool): Whether to print out errors or not.
    - return_type (str): Return format, can be:
        - "list": Places passed as a list
        - "string": Places list converted to string, passed as a string
        - "comma_separated_string": Places list joined with commas, passed as a string

    Returns:
    - str: A string representation of the list of places.
    """
    places = []
    try:
        for place in response["location_dates"]:
            if place["location"] not in places:
                places.append(place["location"])
            elif not silent:
                print(f"{place['location']} already in list (person: {response['name']})")
    except KeyError:
        if not silent:
            print(f"Could not find location_dates in response for person: {response['name']}")
    
    if return_type == "comma_separated_string":
        return ",".join(places)
    if return_type == "string":
        return str(places)
    if return_type == "list":
        return places
    raise ValueError(f"Not known return_type: {return_type}")


def get_places_with_years_from_response(response, silent=True, return_type = "list", dates_separator = ","):
    """
    Extract places with temporal data (years) from the response.

    Parameters:
    - response (dict | str): Either the response dictionary (with person data),
                             or a string representation of response['location_dates'].
    - silent (bool): Whether to print out errors or not.
    - return_type (str): Return format, can be:
        - "list": Places with years passed as a list
        - "string": Places with years list converted to string, passed as a string
        - "semicolon_separated_string": Places with years list joined with semicolons between instances, passed as a string

    Returns:
    - str: String representation of the places with years
    """
    places = []
    if type(response)==str:
        response = stringlist_to_list(response)
        if type(response) == list:
            location_results = response
        elif type(response) == dict:
            location_results = response['location_dates']
    else:
        location_results = response["location_dates"]
    for loc_result in location_results:
        years = get_years_from_response_location(loc_result, silent=silent)
        if years != []:
            min_year = min(years); max_year = max(years)
            #Checking if the location is already in the list
            if not any(p.split(':')[0] == loc_result["location"] for p in places):#Just get the part before the colon, which is the location's name
                places.append(f"{loc_result['location']}:{min_year}-{max_year}")
            else:
                #Find the index of the location in the places list
                for i, p in enumerate(places):
                    if p.split(':')[0] == loc_result["location"]:
                        #Add these years next to the existing years
                        places[i] = f"{p}{dates_separator}{min_year}-{max_year}"
                        break
    if return_type == "semicolon_separated_string":
        return ";".join(places)
    if return_type == "string":
        return str(places)
    if return_type == "list":
        return places
    raise ValueError(f"Not known return_type: {return_type}")


def stringlist_to_list(stringlist):
    """
    Convert a string representation of a list to an actual list.

    Parameters:
    - stringlist (str): The string representation of a list.

    Returns:
    - list: The converted list.
    """
    import ast #library not used for other cases, not worth importing generally
    return ast.literal_eval(stringlist) #but this functionality is already included in it


def results_dataframe(all_people_info: list | dict):
    """
    Create a DataFrame from the list of people's information.

    Parameters:
    - all_people_info (list or dict): The list or dictionary containing the information.

    Returns:
    - DataFrame: The DataFrame containing the information.
    """
    import pandas as pd
    if isinstance(all_people_info, dict):
        return pd.DataFrame.from_dict([all_people_info])
    if isinstance(all_people_info, list):
        return pd.DataFrame.from_dict(all_people_info)
    raise ValueError("Input should be a list or dictionary.")


####################################### Queries for multiple instances (people) #######################################

def get_multiple_people_all_info(people, retries=3, delays=[1, 10, 60]):
    """
    NOTE: Querying multiple people at once is faster than querying them separately, however might miss some instances.
    Definitely consider using 'get_multiple_people_all_info_fast_retry_missing' which runs this function and tries again for missing instances.

    Get all information about multiple people from Wikidata, in one query per chunk (150 instances).

    Parameters:
    - people, retries, delays: See at the top of the file.

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
        response_json = sparql_query(query, retries, delays)
        results = response_json.get('results', {}).get('bindings', [])
        for person_name in chunk:
            person_results = [r for r in results if r.get('personLabel', {}).get('value') == person_name]
            if person_results:
                person_info = create_person_info_from_results(person_name, person_results)
                person_info['id'] = get_id_from_results(person_results)
                all_people_info.append(person_info)
    return all_people_info


def get_multiple_people_all_info_fast_retry_missing(people, retries=3, delays=[1,10,60]):
    """
    Quickly query multiple people at once, then retry for missing instances separately.
    Basically, running 'get_multiple_people_all_info' first, then 'get_all_person_info_strict' for each missing instance separately.
        If there are still missing instances, run 'get_person_all_info_different_languages' to check if they have an instance in non-English Wikipedia.

    Parameters:
    - people, retries, delay: See at the top of the file.

    Returns:
    - list: List of dictionaries for each person.
    """
    gathered_people_parallel = get_multiple_people_all_info(people, retries, delays)
    collected_names = [gathered_people_parallel[k]['name'] for k in range(len(gathered_people_parallel))]
    missing_people = [p for p in people if p not in collected_names]

    gathered_people_separate = []
    for person in missing_people:
        person_info = get_all_person_info_strict(person)
        if person_info:
            gathered_people_separate.append(person_info)
    
    return gathered_people_parallel + gathered_people_separate


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


def get_multiple_people_wikidata_ids(people, retries=3, delays = [1, 10, 60], return_counts=False, return_extended=False, return_most_common=False):
    """
    Retrieve (only) Wikidata IDs for multiple people.
    This is useful to further query information afterwards, using the IDs (which get faster responses).

    Parameters:
    - people, retries, delays: See at the top of the file.
    - return_counts (bool): Whether to return the counts of response results for each person.
    - return_extended (bool): Whether to return the extended results (all IDs) for each person, or just the last one, or...
    - return_most_common (bool): Return the most common ID gathered for each person.

    Returns:
    - dict or tuple: Dictionary of person names and their Wikidata IDs.
    - (optional) dict: Dictionary of person names and their counts of results.

    Warning:
    - If return_most_common and return_extended are both True, only return_extended will be used.
    """
    from collections import Counter
    if return_most_common and return_extended:
        print("Both return_most_common and return_extended are True. Only return_extended will be used.")

    chunks = [people[i:i + 150] for i in range(0, len(people), 150)]
    all_wikidata_ids = {}
    result_counts = {}
    extended_results = {}

    for chunk in chunks:
        people_string = ' '.join(f'"{p}"' for p in chunk)
        query = f'''
        SELECT ?person ?personLabel WHERE {{
          VALUES ?personLabel {{ {people_string} }}
          ?person ?label ?personLabel.
          ?person wdt:P31 wd:Q5.
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],*". }}
        }}
        ''' #?person wdt:P31 wd:Q5. : Ensure instances of humans

        response_json = sparql_query(query, retries, delays)
        if response_json:
            results = response_json.get('results', {}).get('bindings', [])
            for person_name in chunk:
                person_results = [r for r in results if r.get('personLabel', {}).get('value') == person_name]
                result_counts[person_name] = len(person_results)
                if person_results:
                    if return_extended or return_most_common:
                        extended_results[person_name] = [r.get('person', {}).get('value').split('/')[-1]
                                                         for r in person_results if 'entity/Q' in r.get('person', {}).get('value')]
                    else:
                        for result in person_results:
                            person = result.get('person', {}).get('value', None)
                            if person and 'entity/Q' in person:
                                wikidata_id = person.split('/')[-1]
                                all_wikidata_ids[person_name] = wikidata_id
                                break

    if return_most_common:
        most_common_ids = {}
        for person_name, ids in extended_results.items():
            if ids:
                most_common_id = Counter(ids).most_common(1)[0][0]
                most_common_ids[person_name] = most_common_id
        if return_counts:
            return most_common_ids, result_counts
        else:
            return most_common_ids

    if return_counts and return_extended:
        return extended_results, result_counts
    elif return_counts:
        return all_wikidata_ids, result_counts
    elif return_extended:
        return extended_results
    else:
        return all_wikidata_ids


def get_multiple_people_wikidata_ids_retry_missing(people, retries=3, delays = [1, 10, 60]):
    """
    Gather Wikidata IDs for multiple people in one query, then retry missing instances with separate queries.

    Parameters:
    - people, retries, delays: See at the top of the file.

    Returns:
    - dict: Dictionary of person names and their Wikidata IDs.
    """
    gathered_ids_parallel = get_multiple_people_wikidata_ids(people, retries, delays, return_counts=False, return_extended=False, return_most_common=True)
    collected_names = list(gathered_ids_parallel.keys())
    missing_people = [p for p in people if p not in collected_names]

    gathered_ids_separate = {}
    for person in missing_people:
        person_id = get_person_wikidata_id(person)
        if person_id:
            gathered_ids_separate[person] = person_id
    return {**gathered_ids_parallel, **gathered_ids_separate} #concatenated


def get_multiple_people_all_info_by_id(people_ids, retries=3, delay=60):
    """
    Get all information about multiple people from Wikidata by their IDs.

    Parameters:
    - people_ids (list of str): List of Wikidata IDs of the people.
    - retries, delay: See at the top of the file.

    Returns:
    - list: List of dictionaries for each person.
    """
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
    """
    NOTE: Unlike 'get_multiple_people_all_info_fast_retry_missing', here there is no attempt to look for non-English Wikipedia instances.

    Get all information about multiple people from Wikidata by their IDs, with retry for missing instances.

    Parameters:
    - people_ids (list of str): List of Wikidata IDs of the people.
    - retries, delay: See at the top of the file.

    Returns:
    - list: List of dictionaries for each person.
    """
    gathered_people_parallel = get_multiple_people_all_info_by_id(people_ids, retries, delay)
    collected_ids = [gathered_people_parallel[k]['id'] for k in range(len(gathered_people_parallel))]
    missing_people_ids = [id for id in people_ids if id not in collected_ids]

    gathered_people_separate= []
    for person_id in missing_people_ids:
        person_info = get_all_person_info_by_id(person_id)
        if person_info:
            gathered_people_separate.append(person_info)

    return gathered_people_parallel + gathered_people_separate


####################################### Queries for 1 person #######################################
#(SPARQL queries). Exhibitions: see below at "queries by Wikidata ID"

def get_all_person_info(person_name, retries=3, delays = [1, 10, 60]):
    """
    Default function to get all sorts of information about a person from Wikidata.
    This includes the person's name, birth place, birth date, death date, gender, citizenship, occupation, work locations (with time data).

    Parameters:
    - person_name, retries, delays: See at the top of the file.

    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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
        response = sparql_query(query, retries, delays)
        
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
                    'location_dates': [],
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
                    
                    location = result.get('workLocationLabel', {}).get('value', None)
                    if location:
                        location_info = {
                            'location': location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        }
                        if location_info not in person_info['location_dates']:
                            person_info['location_dates'].append(location_info)
                return person_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {person_name}, status code: {response.status_code}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                print(f"Attempt {attempt + 1} of {retries}.")
                time.sleep(delays[attempt])
            else:
                break

    return None


def get_all_person_info_strict(person_name, retries=3, delays=[1, 10, 60], silent = True):
    """
    An improved version of get_all_person_info.
    Basically, same as get_all_person_info but restricts to just human instances
        and gets the ID of the person too, only if it starts with Q.
    Would be for every language, but that also excludes person alias cases.

    Parameters:
    - person_name, retries, delays, silent: See at the top of the file.

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

    response_json = sparql_query(query, retries, delays)
    if response_json:
        results = response_json.get('results', {}).get('bindings', [])
        id = get_id_from_results(results)
        if id:
            person_info = create_person_info_from_results(person_name, results)
            person_info['id'] = id
            return person_info
        else:
            if not silent:
                print(f"{person_name} has no valid ID.")
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

    response_json = sparql_query(query, retries, delay)
    if response_json:
        results = response_json.get('results', {}).get('bindings', [])
        if results:
            for result in results:
                #person = result.get('person', {}).get('value', None) #wd:*Wikidata ID*
                label = most_common_results(['personLabel'], results)
                if label:
                    return label
    return None


def get_person_wikidata_name_fast(person_name, retries = 3, delays=[1, 10, 60]):
    """
    Get the Wikidata database name of a person by their (alias) name.

    Parameters:
    - person_name, retries, delays: See at the top of the file.

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
            time.sleep(delays[attempt])
        elif response.status_code in [400, 404]:
            print("Error: %s"%response.status_code, "person name: ", person_name)
            return None
    return None


def get_person_aliases(person_name):
    """
    TODO
    Get aliases and different language names for a person.
    """
    #TODO
    #both aliases - and different language names
    #plan: if given as an ID, query the ID, get all names for each language AND the "also known as" aliases
          #if given as a name, query the name, get the (most common) ID, then do the same as above
    pass


def get_person_locations(person_name, retries=3, delay=1):
    """
    Get all work locations of a person from Wikidata.
    
    Parameters:
    - person_name, retries, delay: See at the top of the file.
    
    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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
    response_json = sparql_query(query, retries, delay)    
    if response_json: #Successful
        results = response_json.get('results', {}).get('bindings', [])
        if results:
            person_locs = create_person_info_from_results(person_name, results)
            return {'name': person_name, 'locations': person_locs['locations'],
                    'location_dates': person_locs['location_dates']}
    return None

######## Queries with or by Wikidata ID ########
def get_person_wikidata_id(person_name, retries = 3, delays = [1, 10, 60]):
    """
    Get the Wikidata ID of a person by their name.
    
    Parameters:
    - person_name, retries, delays: See at the top of the file.
    
    Returns:
    - str or None: Wikidata ID (starting with a Q) of the person if successful, None otherwise"""
    query = '''
    SELECT ?person ?personLabel WHERE{
    ?person ?label "%s"@en.
    ?person wdt:P31 wd:Q5.  #Ensure it's an instance of human, could happen that it's a statue of the person or something
    SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }
    }
    '''% person_name.replace('"', '\"')

    response_json = sparql_query(query, retries, delays)
    results = response_json.get('results', {}).get('bindings', [])
    if results:
        ids= [result['person']['value'].split('/')[-1] for result in results]
        acceptable_ids = [i for i in ids if re.match(r'^Q\d+$', i)]
        if acceptable_ids:
            return get_id_from_results(results)
        else:
            print(f"{person_name} has no valid IDs (none in the form Q12345..)")
    return None


def get_all_person_info_by_id(person_id, retries=3, delays=[1,10,60], silent = True):
    """
    NOTE: Exhibitions are excluded currently, as they are too slow for some artists (e.g. Rubens).
    Get all information about a person from Wikidata, using their Wikidata ID.
    
    Parameters:
    - person_id, retries, delays, silent: See at the top of the file.
    
    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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

    response_json = sparql_query(query, retries, delays)
    results = response_json.get('results', {}).get('bindings', [])
    if results:
        person_info = create_person_info_from_results_with_id(person_id, results)
        return person_info
    return None


def get_exhibitions_by_id(person_id, retries=3, delays=[1, 10, 60], silent = True):
    """
    Get exhibitions of a person from Wikidata, using their Wikidata ID.

    Parameters:
    - person_id, retries, delays, silent: See at the top of the file.

    Returns:
    - list or None: List of exhibitions of the person if successful, None otherwise.
    """
    query = '''
    SELECT ?person ?personLabel ?collectionLabel WHERE {
      BIND(wd:%s AS ?person)
      OPTIONAL { ?person wdt:P6379 ?collection. }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". ?person rdfs:label ?personLabel. ?collection rdfs:label ?collectionLabel. }
    }
    ''' % person_id

    response_json = sparql_query(query, retries, delays)    
    if response_json:
        results = response_json.get('results', {}).get('bindings', [])
        if not silent:
            print('Results 0:', results[0])
        if results:
            collections = [result.get('collectionLabel', {}).get('value', None) for result in results if 'collectionLabel' in result]
            return collections
    return None


def get_all_person_info_and_exhibitions_by_id(person_id, retries=3, delays = [1, 10, 60], silent = True):
    #This may be too slow for some artists, e.g. Rubens, therefore we get an error (query 1 minute timeout)
    """
    NOTE: This may be too slow for some artists, e.g. Rubens, for whom we can get a timeout error.
    Consider using get_all_person_info_by_id and get_exhibitions_by_id successively.

    Get all information about a person from Wikidata, using their Wikidata ID, including exhibitions.

    Parameters:
    - person_id, retries, delays, silent: See at the top of the file.

    Returns:
    - dict or None: Data dictionary about the person if successful, None otherwise.
    """
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

    response_json = sparql_query(query, retries, delays)
    if response_json:
        results = response_json.get('results', {}).get('bindings', [])
        if not silent:
            print('Results 0:', results[0])
        if results:
            person_info = create_person_info_from_results_with_id(person_id, results)
            return person_info
    return None
