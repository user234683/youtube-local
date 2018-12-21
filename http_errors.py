class Code2xx(Exception):
    pass
class Code200(Code2xx):
    pass

class Error4xx(Exception):
    pass
class Error404(Error4xx):
    pass

class Error5xx(Exception):
    pass
class Error500(Error5xx):
    pass
class Error502(Error5xx):
    pass
