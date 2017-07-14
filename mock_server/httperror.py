import json

def default_response(status_code,**kwargs):    
    if status_code == 401:
        return (__get_401(missing_key=kwargs.get('missing_key')), [("Content-Type", "text/json")])
    if status_code == 404:
        return (__get_404(url_path=kwargs.get('url_path'),
                       method=kwargs.get('method'),
                       out=kwargs.get('out')), [("Content-Type", "text/html")])

def __get_404(**kwargs):
    method = kwargs.get('method') if kwargs.get('method') else 'GET'
    return '<p>Api response is not defined</p><br/>'\
           '<a href="/__manage/create?url_path={}&'\
           'method={}&status_code=404&format={}">'\
           'create resource method</a>'.format(kwargs.get('url_path'),
                                               method,
                                               kwargs.get('out'))
def __get_401(**kwargs):
    content = {'id':'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx',
     'status':'401',
     'code':'TSP-200',
     'errorMessage':"Required {} missing.".format(', '.join(kwargs.get('missing_key'))),
     'stackTrace':'...........'}
    return json.dumps(content)

if __name__ == '__main__':
    print default_response(401,missing_key=['a','b','c'])
    print get_404(url_path='/',method='GET',out='json')