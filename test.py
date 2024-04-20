import streamlit as st
import pandas as pd
import numpy as np
import requests
import ast
import webbrowser
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
st.set_page_config(layout="wide")
import datetime

import mysql.connector
from mysql.connector import Error

def login():
    st.title("Movie Recommendation System Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    st.markdown("New User? [Register Here](?page=registration)")
 
    
    login_button = st.button("Login")
    
    if login_button:
        try:
            conn = mysql.connector.connect(
                host='localhost',
                database='users',
                user='root',
                password=''
            )
            if conn.is_connected():
                cursor = conn.cursor()
                query = f"SELECT * FROM userdata WHERE username='{username}' AND password='{password}'"
                cursor.execute(query)
                user = cursor.fetchone()
                if user:
                    st.success("Login successful!")
                    st.experimental_set_query_params(username=username, page="recommendation")
                else:
                    st.warning("Invalid credentials!")
        except Error as e:
            st.error(f"Error connecting to MySQL database: {e}")
        finally:
            conn.close()


def registration():
    st.title("Movie Recommendation System Registration")
    name = st.text_input("Name")
    age = st.number_input("Age", min_value=1, max_value=120)
    gender = st.selectbox("Gender", ["Male", "Female", "Other"])
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    favourite_genre = st.text_input("Favourite Genre")
    register_button = st.button("Register")
    if register_button:
        try:
            cnx = mysql.connector.connect(user='root', password='',
                                          host='localhost', database='users')
            cursor = cnx.cursor()

            add_user = ("INSERT INTO userdata "
                        "(name, age, gender, username, password, favouritegenre) "
                        "VALUES (%s, %s, %s, %s, %s, %s)")
            user_data = (name, age, gender, username, password, favourite_genre)
            cursor.execute(add_user, user_data)
            cnx.commit()

            st.success("Registration successful!")
            
        except mysql.connector.Error as err:
            st.error(f"Error: {err}")

        finally:
            cursor.close()
            cnx.close()
    st.markdown("Go back [login](?/)")


def recommendation():
    st.title("Movie Recommendation System")
    movies = pd.read_csv('tmdb_5000_movies.csv')
    critic_reviews = pd.read_csv('rotten_tomatoes_critic_reviews.csv')
    critic_reviews = critic_reviews.loc[critic_reviews['top_critic']==True].drop_duplicates(subset=['rotten_tomatoes_link'], keep='first')
    critic_reviews = critic_reviews[['rotten_tomatoes_link', 'review_score']]
    movies_reviews = pd.read_csv('rotten_tomatoes_movies.csv')
    movies_reviews = movies_reviews.rename(columns={'movie_title': 'original_title'})
    movies_reviews = pd.merge(movies_reviews, critic_reviews, on='rotten_tomatoes_link', how='left')
    movies_reviews = movies_reviews.drop_duplicates(subset=['original_title'])
    movies = pd.merge(movies, movies_reviews[['original_title', 'review_score']], on='original_title', how='left')
    cnx = mysql.connector.connect(user='root', password='', host='localhost', database='users')
    cursor = cnx.cursor()
    username = st.experimental_get_query_params().get("username", [None])[0]
    cursor.execute(f"SELECT favouritegenre, age, gender,name FROM userdata WHERE username = '{username}'")
    user_info = cursor.fetchone()
    favourite_genre = user_info[0]
    age = user_info[1]
    gender = user_info[2]
    name=user_info[3]
    st.write(f"Welcome {name}!")
    filtered_movies = movies[movies['genres'].apply(lambda x: favourite_genre in [genre['name'] for genre in ast.literal_eval(x)])]
    current_year = datetime.datetime.now().year
    filtered_movies = filtered_movies[filtered_movies['release_date'].apply(lambda x: int(x.split('-')[0]) >= (current_year - age))]
    #if gender != 'any':
    #   filtered_movies = filtered_movies[filtered_movies['cast'].apply(lambda x: gender.lower() in [actor['gender'].lower() for actor in ast.literal_eval(x)])]

    
    final_movies = pd.concat([filtered_movies, movies], axis=0).drop_duplicates(subset=['id']).reset_index(drop=True)

    
    tfidf = TfidfVectorizer(stop_words='english')
    final_movies['original_language'] = final_movies['original_language'].str.lower()
    final_movies['genres'] = final_movies['genres'].apply(ast.literal_eval)
    final_movies['genre_names'] = final_movies['genres'].apply(lambda x: [genre['name'] for genre in x])
    final_movies['features'] = final_movies['overview'] + ' ' + final_movies['genre_names'].apply(lambda x: ' '.join(x)) + ' ' + final_movies['original_language'] + ' ' + final_movies['popularity'].astype(str) + ' ' + final_movies['vote_average'].astype(str)
    final_movies['features'] = final_movies['features'].fillna('')
    tfidf_matrix = tfidf.fit_transform(final_movies['features'])
    similarity = linear_kernel(tfidf_matrix, tfidf_matrix)
    title_selected = st.selectbox('What is your favourite movie?', movies['title'].values)
    
    def fetch_poster(movie_id):
        response=requests.get('https://api.themoviedb.org/3/movie/{}?api_key=b932b1d1e2ececff2526ed681d352714&language=en-US'.format(movie_id))
        data=response.json()
        return 'https://image.tmdb.org/t/p/w500/'+data['poster_path']
    
    def recommend(movie):
        index_of_the_movie = movies[movies['title'] == movie].index[0]
        similarity_score = list(enumerate(similarity[index_of_the_movie]))
        sorted_similar_movies = sorted(similarity_score, key=lambda x: x[1], reverse=True)[1:6]
        recommended_movie=[]
        recommended_posters=[]
        for i in sorted_similar_movies:
            movie_id=movies.iloc[i[0]].id
            recommended_movie.append(movies.iloc[i[0]].title)
            recommended_posters.append(fetch_poster(movie_id))
        return recommended_movie, recommended_posters
    df1 = pd.read_csv('hotstar1.csv')
    df2 = pd.read_csv('netflix.csv')
    if st.button('Recommend'):
        titles, posters = recommend(title_selected)
        links = []
        for i in range(len(titles)):
            for j in range(len(df1)):
                if titles[i] == df1['Movie Name'][j]:
                    links.append(('c'+str(i+1), df1['Movie Link'][j], 'hotstar'))
                    break
            for j in range(len(df2)):
                if titles[i] == df2['MovieName'][j]:
                    links.append(('c'+str(i + 1), df2['Link'][j], 'netflix'))
                    break
        c1, c2, c3, c4, c5 = st.columns(5)
        columns = st.columns(5)
        for i in range(len(titles)):
            with columns[i]:
                z = 0
                st.text(titles[i])
                st.image(posters[i])
                for j in links:
                    if j[0] == f'c{i+1}':
                        k = f'[Watch this on {j[2]}]({j[1]})'
                        st.markdown(k, unsafe_allow_html=True)
                        z = 1
                if z == 0:
                    st.markdown("not available on hotstar/netflix")

        
    st.markdown("""
    <style>
    .big-font {
        font-size:25px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown('<p class="big-font">Popular Movies:</p>', unsafe_allow_html=True)

    sort_popular = movies.sort_values(by=['popularity'], ascending=False)[1:6]
    popular_movie = sort_popular['id'].tolist()
    popular_title = sort_popular['title'].tolist()
    popular_posters = [fetch_poster(i) for i in popular_movie]


    links1 = []
    for i in range(len(popular_title)):
        for j in range(len(df1)):
            if popular_title[i]==df1['Movie Name'][j][:-1]:
                links1.append(('c'+str(i+1),df1['Movie Link'][j],'hotstar'))
                break
        for j in range(len(df2)):
            if popular_title[i]==df2['MovieName'][j]:
                links1.append(('c'+str(i+1),df2['Link'][j],'netflix'))
                break


    cols = st.columns(5)
    for i, col in enumerate(cols):
        with col:
            st.text(popular_title[i])
            st.image(popular_posters[i])
            z = 0
            for link in links1:
                if link[0] == 'c'+str(i+1):
                    k = '[Watch this on {}]({})'.format(link[2], link[1])
                    st.markdown(k, unsafe_allow_html=True)
                    z = 1
            if z == 0:
                st.markdown("not available on hotstar/netflix")


if "page" not in st.experimental_get_query_params():
    login()
elif st.experimental_get_query_params()["page"][0] == "registration":
    registration()
else:
    recommendation()
