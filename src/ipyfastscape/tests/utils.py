def counter_callback():
    counter = {'called': 0}

    def callback(*args, **kwargs):
        counter['called'] += 1

    return counter, callback
