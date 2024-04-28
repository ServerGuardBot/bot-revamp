SELECT * FROM feeddata WHERE
    url == $url OR meta::id(id) == $id