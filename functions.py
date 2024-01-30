def get_artist_locations(artist_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    import requests
    import time

    #SPARQL query
    query = '''
    SELECT ?artist ?artistLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime WHERE {
      ?artist ?label "%s"@en.
      ?artist wdt:P19 ?placeOfBirth.
      ?artist wdt:P569 ?dateOfBirth.
      ?artist wdt:P570 ?dateOfDeath.
      ?artist wdt:P20 ?placeOfDeath.
      OPTIONAL {
        ?artist p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ''' % artist_name.replace('"', '\"')
    #We already have birth data, so this function will not be used

    #Attempts till we get a response / 'retries' goes over the limit
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                artist_info = {
                    'name': artist_name,
                    'birth_place': results[0].get('placeOfBirthLabel', {}).get('value', None),
                    'death_place': results[0].get('placeOfDeathLabel', {}).get('value', None),
                    'work_locations': [],
                }
                for result in results:
                    work_location = result.get('workLocationLabel', {}).get('value', None)
                    if work_location:
                        artist_info['work_locations'].append({
                            'location': work_location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        })
                return artist_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {artist_name}, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None


def get_artist_info(artist_name, endpoint_url="https://query.wikidata.org/sparql", retries=3, delay=1):
    import requests
    import time

    #SPARQL query
    query = '''
    SELECT ?artist ?artistLabel ?placeOfBirthLabel ?dateOfBirth ?dateOfDeath ?placeOfDeathLabel ?workLocationLabel ?startTime ?endTime ?pointInTime WHERE {
      ?artist ?label "%s"@en.
      ?artist wdt:P19 ?placeOfBirth.
      ?artist wdt:P569 ?dateOfBirth.
      ?artist wdt:P570 ?dateOfDeath.
      ?artist wdt:P20 ?placeOfDeath.
      OPTIONAL {
        ?artist p:P937 ?workStmt.
        ?workStmt ps:P937 ?workLocation.
        OPTIONAL { ?workStmt pq:P580 ?startTime. }
        OPTIONAL { ?workStmt pq:P582 ?endTime. }
        OPTIONAL { ?workStmt pq:P585 ?pointInTime. }
      }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    ''' % artist_name.replace('"', '\"')
    #We already have birth data, so this function will not be used

    #Attempts till we get a response / 'retries' goes over the limit
    for attempt in range(retries):
        response = requests.get(endpoint_url, params={'query': query, 'format': 'json'})
        
        if response.status_code == 200: #Successful
            data = response.json()
            results = data.get('results', {}).get('bindings', [])
            if results:
                artist_info = {
                    'name': artist_name,
                    'birth_place': results[0].get('placeOfBirthLabel', {}).get('value', None),
                    'birth_date': results[0].get('dateOfBirth', {}).get('value', None),
                    'death_date': results[0].get('dateOfDeath', {}).get('value', None),
                    'death_place': results[0].get('placeOfDeathLabel', {}).get('value', None),
                    'work_locations': [],
                }
                for result in results:
                    work_location = result.get('workLocationLabel', {}).get('value', None)
                    if work_location:
                        artist_info['work_locations'].append({
                            'location': work_location,
                            'start_time': result.get('startTime', {}).get('value', None),
                            'end_time': result.get('endTime', {}).get('value', None),
                            'point_in_time': result.get('pointInTime', {}).get('value', None),
                        })
                return artist_info
            break #Don't need to try again, we have the data
        else: #Some status codes are handled,it's fine now
            print(f"Error fetching data for {artist_name}, status code: {response.status_code}. Attempt {attempt + 1} of {retries}.")
            if response.status_code in [429, 500, 502, 503, 504]:
                time.sleep(delay)
            else:
                break

    return None

