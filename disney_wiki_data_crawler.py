from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
import re
import time
import json
from dateutil.parser import parse
import pandas as pd

# Full selenium import below to access shadow elements without opening up a physical browser tab.
import selenium
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)


# main function that pulls a list of dictionaries compiled through disney_list_crawler() and saves it to a json file
# using save_data()
def main():
    save_data('disney_data.json', disney_list_crawler())


# This is the function that parses through the movie links on wikipedia's list of walt disney movies, and returns a list
# of dictionaries containing the relevant data from each movie link.
def disney_list_crawler(url='https://en.wikipedia.org/wiki/List_of_Walt_Disney_Pictures_films', start=0):
    site = requests.get(url)
    soup = BeautifulSoup(site.content, 'html.parser')
    tables = soup.find('div', {'id': 'bodyContent'}).select('table.wikitable.sortable i a')
    disney_links = [urljoin(url, a['href']) for a in tables]
    dict_list = []
    limit = len(disney_links)
    count = 1
    for i in range(start, limit):
        movie_dict = wiki_table_dict(disney_links[i], count)
        imdb = imdb_ratings(disney_links[i])
        rt = rt_ratings(disney_links[i])
        if movie_dict:
            if imdb:
                movie_dict = movie_dict | imdb
            if rt:
                movie_dict = movie_dict | rt
            dict_list.append(movie_dict)
        else:
            continue
        if count % 25 == 0:
            print(f'Completed through link # {count}')
        count += 1
        time.sleep(1)

    return dict_list


# This is the function utilized in disney_list_crawler() for the bulk of the information gathered. It parses a movie
# link and returns a dictionary containing all of the information stored within the infobox.
def wiki_table_dict(link, count):
    try:
        local_url = requests.get(link)
        local_soup = BeautifulSoup(local_url.content, 'html.parser')
        clean_references(local_soup)
        table = []

        try:
            table = local_soup.select('table.infobox tbody')[0].find_all('tr')
        except IndexError as e:
            print(f'Page: {link} has no infobox')

        contents = dict()
        for tr in table:
            if tr.find('th'):

                # Takes the title of the infobox and pairs it to the key 'Title'
                if tr.select('th.summary'):
                    contents['Title'] = tr.get_text(' ', strip=True)

                # Formats the release date as a date object
                elif re.search(r'[R|r]elease', tr.find('th').get_text(' ', strip=True)):
                    first_date = tr.find('td').get_text(' ', strip=True).replace('\xa0', ' ').split('(')[0]
                    contents[tr.find('th').get_text(' ', strip=True)] = parse(first_date).date().isoformat()

                # Takes td tags with an already formatted list of text elements, and returns a list of those elements
                # paired with the relevant key
                elif tr.select('td div.plainlist'):
                    contents[tr.find('th').get_text(' ', strip=True)] = \
                        [li.get_text(' ', strip=True).replace('\xa0', ' ') for li in tr.find_all('li')]

                # This lengthy statement handles all other relevant information
                elif tr.select('th') and tr.select('td'):

                    # Formats the running time to strip the words and return only the number of minutes as an integer.
                    if tr.find('th').get_text(' ', strip=True) == 'Running time':
                        contents[tr.find('th').get_text(' ', strip=True)] = \
                            int(re.sub('[^0-9]', ' ', tr.find('td').get_text()).split()[0])

                    # Formats dollar amounts as an integer value, handling all edge cases using convert_money_value()
                    elif '$' in tr.find('td').get_text():
                        contents[tr.find('th').get_text(' ', strip=True)] = \
                            convert_money_value(tr.find('td').get_text(' ', strip=True).replace('\xa0', ' '))

                    # Checks for infobox elements that don't have a div list, but do have multiple relevant text
                    # elements embedded in one td tag. This statements splits the text into individual list elements,
                    # rather than a single string element.
                    elif len(tr.select('td')[0].find_all('a')) > 1:
                        contents[tr.find('th').get_text(' ', strip=True)] = \
                            [a.get_text(' ', strip=True).replace('\xa0', ' ') for a in tr.find('td').find_all('a')]

                    # This is the final catch all statement, after the odd cases have been taken care of. This statement
                    # returns the key and value of a td tag with a single text element.
                    else:
                        contents[tr.find('th').get_text(' ', strip=True)] = \
                            [tr.find('td').get_text(' ', strip=True).replace('\xa0', ' ')]

        return contents

    except Exception as e:
        print('------')
        print(f'line {count} failed {e}')
        print(f'Link: {link}')
        print('------')


# convert_money_value() takes the text returned from data that is formatted as a dollar amount, and returns the text
# converted into an analyzable integer.
def convert_money_value(value_string):
    division = value_string.split('$')
    comp = re.sub(r'\)', ' ', division[-1]).split()
    num = ''.join([comp[i] for i in range(len(comp)) if re.search(r'\d', comp[i])][0])
    conv = float(re.sub(r'[-–]', ' ', re.sub(r'[><,]', '', num)).split()[0])
    if 'million' in comp:
        conv = conv*1000000
    elif 'billion' in comp:
        conv = conv*1000000000
    return int(conv)


# clean_references() cleans any reference links from the table data in each row that we are parsing.
def clean_references(soup_object):
    for tag in soup_object.find_all('sup'):
        tag.decompose()


# Function that expands an individual shadow root, employed by get_shadow_element().
def expand_shadow_element(element):
    shadow_root = driver.execute_script('return arguments[0].shadowRoot', element)
    return shadow_root


# Accesses Rotten Tomatoes #shadow-root elements. This function returns the two review percentages as a dictionary.
def get_shadow_elements(link):
    driver.get(link)
    root1 = driver.find_element_by_tag_name('score-board')
    shadow_root1 = expand_shadow_element(root1)

    meter_root = shadow_root1.find_elements_by_css_selector('div.tomatometer-container')[0]
    meter_root1 = meter_root.find_element_by_tag_name('score-icon-critic')
    meter_root2 = expand_shadow_element(meter_root1)
    tomatometer = meter_root2.find_element_by_css_selector('span.percentage.big').text

    audience_root = shadow_root1.find_elements_by_css_selector('div.audience-container')[0]
    audience_root1 = audience_root.find_element_by_tag_name('score-icon-audience')
    audience_root2 = expand_shadow_element(audience_root1)
    audience = audience_root2.find_element_by_css_selector('span.percentage.big').text

    return {'Rotten Tomatoes Critic': tomatometer, 'Rotten Tomatoes Audience': audience}


# Finds the IMDb link in the external references of a given wikipedia page. It uses this to pull the score out of 10
# from that page for the title of the given movie link
def imdb_ratings(link):
    site = requests.get(link)
    local_soup = BeautifulSoup(site.content, 'html.parser')
    try:
        imdb_selector = re.compile('https://www.imdb.com/title/.*/$')
        imdb_links = local_soup.select("div#mw-content-text a[href^='https://www.imdb.com/title/']")
        imdb_link = [link['href'] for link in imdb_links if imdb_selector.match(link['href'])][0]
        imdb_site = requests.get(imdb_link)
        imdb_soup = BeautifulSoup(imdb_site.content, 'html.parser')
        imdb_rating = imdb_soup.find('span', {'itemprop': 'ratingValue'})
        return {'IMDb Rating': imdb_rating.get_text()}

    except IndexError as e:
        print('---')
        print(f'{link} has no IMDb data')
        print('---')

    except AttributeError as e1:
        print('---')
        print(f'Could not find data in {imdb_link} because {e1}')
        print('---')


# Finds the Rotten Tomatoes link in the external references of a given wikipedia page. It uses this to pull both the
# critical and audience rating percentages, returning them as a dictionary.
def rt_ratings(link):
    site = requests.get(link)
    local_soup = BeautifulSoup(site.content, 'html.parser')
    try:
        rt_link = local_soup.select("div#mw-content-text a[href^='https://www.rottentomatoes.com/m/']")[0]['href']
        ratings = get_shadow_elements(rt_link)
        return ratings

    except IndexError as e:
        print('----')
        print(f'{link} has no Rotten Tomatoes data')
        print('----')

    except selenium.common.exceptions.NoSuchElementException as e1:
        print('----')
        print(f'Could not find data in {rt_link} because {e1}')
        print('----')

    except selenium.common.exceptions.TimeoutException as e2:
        print('----')
        print(f'Selenium took too long trying to access the data from {rt_link}, {e2}')
        print('----')


# save_data() allows us to quickly save data to a json file, utilized in main() where our data is the dictionary list
# captured through disney_list_crawler().
def save_data(title, data):
    with open(title, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# load_data() gives us the ability to load our json data into our pycharm terminal if we so choose.
def load_data(title):
    with open(title, encoding='utf-8') as file:
        return json.load(file)


#main()


#data = load_data('disney_data.json')
#data_frame = pd.DataFrame(data)
#data_frame.to_csv('disney_data_analyzable.csv')
