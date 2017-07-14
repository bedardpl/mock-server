# -*- coding: utf-8 -*-

import os, sys
import re
from . import api
from . import util
from . import httperror
import tornado.httpclient
import json

from email.parser import Parser

class FilesMockProvider(api.FilesMockProvider):
    
    def loadjson(self,jsondoc):
        try:return json.loads(jsondoc.replace("'",'"'))
        except:return {}

    def __call__(self, request, method, data, uri='', status_code=200, format="json"):
        # print "*"*35
        # print "request:\t{}\nmethod:\t{}\ndata:\t{}\nuri:\t{}\nstatus_code:\t{}\nformat:\t{}".format(request, method, data, uri, status_code, format)
        # print "*"*35
        
        self._request = request
        self._status_code = status_code
        self._method = self._request.method
        self._body = data.replace("'",'"') if data is not None else ''
        self._format = format
        self._uri = uri
        req_key_path = None
        inreq = None
        
        self._body =  self.loadjson(self._body)
        
        # prepare response
        response = api.Response()

        # get paths
        paths = self._get_path(self._get_filename())
        if not paths:
            return self._error(response, status_code=404,
                               url_path=self._request.url_path)

        content_path, file_url_path = paths
        content = self._get_content(content_path)
        headers_path = os.path.join(file_url_path, self._get_header_filename())
        
        # get the required key from the body of the request
        req_key_path = os.path.join(file_url_path, self._get_required_key())
        try:
            req_key = json.loads(self._get_required_keys(req_key_path))
        except:
            req_key = {'required_key':[]}
        
        #that happen in the case no response file has been created for a given request
        if content is None:
            return self._error(response,status_code=404,
                               url_path=paths,method=self._method,
                               out=self._format)
        
        if self._method == 'POST':
            # retrieve all key from the query that are in the required key array 
            inreq = [y for y in self._body.keys() if y in req_key.get('required_key')]
        elif self._method == 'GET':
            # retrieve url parameter
            urlsplit=self._uri.split("?")
            if len(urlsplit) > 1:
                url_param = [x.split("=")[0] for x in urlsplit[1].split("&")]
            else:
                url_param = []
            inreq = [y for y in url_param if y in req_key.get('required_key')]
        
        # compare the lenght of that previously created list with the required_key lenght
        got_all_required = True if len(inreq) >= len(req_key.get('required_key')) else False
        # if we don't have all required return error 401
        if not got_all_required:
            return self._error(response,
                               status_code=401,
                               missing_key=[x for x in req_key.get('required_key') if x not in inreq])
        
        response.status_code = status_code
        response.content = content
        response.headers = self._get_headers(headers_path)
        
        # print("{}".format(response))
        
        return response

    def _error(self, response, status_code=404, **kwargs):
        self.error = 1
        answer = httperror.default_response(status_code=status_code,**kwargs)
        response.status_code, response.content, response.headers = status_code, answer[0], answer[1]
        return response
    
    def _get_required_keys(self, regpath):
        rval=''
        try:
            rval = util.read_file(regpath)
        except:
            print "{}:\texception:\t{}".format(regpath,sys.exc_info()[1])
            rval = {}
        return rval
    
    def _get_content(self, content_path):
        rval={}
        try:
            rval = util.read_file(content_path)
        except:
            print "{}:\texception:\t{}".format(content_path,sys.exc_info()[1])
        return rval

    def _get_headers(self, headers_path):
        headers = []

        if not os.path.isfile(headers_path):
            return headers

        try:
            with open(headers_path) as f:
                strip = lambda s: s if len(s) == 0 \
                    else s[0] + s[1:].strip()
                return list(Parser().parsestr(
                    "\r\n".join(map(strip, f.readlines()))).items())
        except IOError:
            return headers

    def _get_filename(self):
        return "%s_%s.%s" % (self._request.method,
                             self._status_code, self._format)
    
    def _get_required_key(self):
        return "{}_req_key_{}.{}".format(self._request.method, self._status_code,self._format)

    def _get_header_filename(self):
        return "%s_H_%s.%s" % (self._request.method,
                               self._status_code, self._format)
    
    def _get_path(self, filename):
        url_path = re.sub("/{2,}", "/", self._request.url_path, count=1)
        content_path = os.path.join(self._api_dir, url_path, filename)

        if os.path.isfile(content_path):
            return content_path, os.path.join(self._api_dir, url_path)

        if url_path.endswith("/"):
            url_path = url_path[:-1]

        if "/" not in url_path:
            return None

        path_regex = []
        for item in url_path.split("/"):
            path_regex.append("(%s|__[^\/]*)" % item)
        c = re.compile("%s%s" % (self._api_dir, "/".join(path_regex)))

        for path in os.walk(self._api_dir):
            m = c.match(path[0])
            if m:
                return os.path.join(path[0], filename), path[0]
        return None

def get_desired_response(provider, request, method, data, uri, status_code=200, format="json"):
    response = provider(request, method, data, uri, status_code, format)
    return response

def resolve_request(provider, method, url_path, data, uri,
                    status_code=200, format="json"):
    request = api.Request(method, url_path, body=data, uri=uri)
    return get_desired_response(
        provider, request, method, data, uri, status_code, format)

def default_response(method, url_path, status_code, format):
    content = \
        'Api response is not defined, <a href="/__manage/create?url_path=%s&'\
        'method=%s&status_code=%d&format=%s">create resource method</a>' %\
        (url_path, method, status_code, format)
    return content, [("Content-Type", "text/html")]

class UpstreamServerProvider(api.UpstreamServerProvider):

    def __init__(self, upstream_server):
        super(UpstreamServerProvider, self).__init__(upstream_server)

        self._http_client = None
        self._request_handler_callback = None

    @property
    def http_client(self):
        if self._http_client is None:
            self._http_client = tornado.httpclient.AsyncHTTPClient()

        return self._http_client

    def __call__(self, data, request_handler_callback):
        self._request_handler_callback = request_handler_callback
        self._data = data

        if data["method"] in ("POST", "PATCH", "PUT"):
            body = data["body"]
        else:
            body = None

        if "If-None-Match" in data["headers"]:
            del data["headers"]["If-None-Match"]

        self.http_client.fetch(
            "%s%s" % (self.upstream_server, data["uri"]),
            callback=self._on_response, method=data["method"],
            body=body, headers=data["headers"], follow_redirects=True)

    def _on_response(self, response):
        if response.error:
            data = response.body
            data, headers = default_response(
                self._data["method"], self._data["uri"],
                self._data["status_code"], self._data["format"])
            status_code = 404
        else:
            data = response.body
            headers = list(response.headers.items())
            status_code = response.code

        self._request_handler_callback(
            api.Response(data, headers, status_code))

if __name__ == "__main__":

    provider = FilesMockProvider("/Users/tomashanacek/Downloads/api")

    print(resolve_request(provider, "post", "/ble"))
    print(resolve_request(provider, "get", "/user/tomas/family/marek"))

    print(resolve_request(provider, "get", "/user/dsfsd"))
    print(resolve_request(provider, "get", "/dsf"))
