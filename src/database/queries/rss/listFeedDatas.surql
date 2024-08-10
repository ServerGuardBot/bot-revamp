SELECT * FROM feeddata WHERE
    $urls CONTAINS url OR $ids CONTAINS meta::id(id);