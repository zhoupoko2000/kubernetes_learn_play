import os
import re
import json
import uuid
import base64
import http.server
import ssl
from io import BytesIO
from functools import reduce

from jinja2 import Environment, FileSystemLoader

def read_file_as_str(path_str):
    with open(path_str, "r") as content_file:
        content = content_file.read()
        return content

def _strip(something):
    if something:
        something = str(something).strip()
    if something:
        return something
    return False

# deep_get help you to get nested dict component
# sample_dict = {"request": {"object": {"metatdata": {"annotations": 1}}}}
# deep_get(sample_dict, "request.object.metatdata") will output {"annotations": 1}
# in later code, you find this deep_get is bound to template attr get, which can be used or called in jinja2 template file

def deep_get(some_dict, keys, default=None):
    return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), some_dict)


class MutatingWebhook:
    def __init__(self, admission_dir, admission_env_path=None):
        if not admission_dir or not os.path.isdir(admission_dir):
            raise Exception("Admission dir must be a valid directory")

        self.jinja_env = Environment(loader=FileSystemLoader(admission_dir))
        self.allow_templates = self._process_templates("allow")
        self.reject_templates = self._process_templates("reject")
        self.mutate_templates = self._process_templates("mutate")

        self.admission_env = {}
        if admission_env_path:
            admission_env_str = read_file_as_str(admission_env_path)
            self.admission_env = json.loads(admission_env_str)

    # subdir is like "allow", "mutate"...
    def _process_templates(self, subdir):
        re = []
        a_path = os.path.join(self.admission_dir, subdir)

        if not os.path.isdir(a_path):
            return re

        for a_rule in os.listdir(a_path):
            full_path = os.path.join(a_path, a_rule)
            patch = os.path.splitext(full_path)
            if patch[1] != ".rule":
                continue

            tm = self.jinja_env.from_string(read_file_as_str(full_path))
            re.append({"name": a_rule, "template": tm})

        return re

    def _patch_request(self, request=None, request_path=None):
        c = dict(request)
        c["env"] = {}
        c["path"] = request_path
        for k in self.admission_env.keys():
            c["env"][k] = self.admission_env[k]

        return c

    def _render(self, template_stuff, request, request_path=None):
        def get_helper(key):
            return deep_get(patched_request, key)
        template = template_stuff["template"]
        template.globals["get"] = get_helper
        patched_request = self._patch_request(request=request, request_path=request_path)
        rendered = template.render(patched_request)
        stripped = _strip(rendered)
        return stripped

    def _is_present(self, request, templates):
        # if no template return False refer to testcases 02 series
        for rule in templates:
            r = self._render(rule, request)
            if r:
                return r
        return False

    def is_allowed(self, request=None):
        return self._is_present(request, self.allow_templates)

    def is_rejected(self, request=None):
        return self._is_present(request, self.allow_templates)

    def build_patchset(self, request=None, request_path=""):
        re = []
        for mutate_rule in self.mutate_templates:
            r = self._render(mutate_rule, request, request_path)
            if not r:
                continue
            try:
                patches = json.loads(r)
            except json.decoder.JSONDecodeError as e:
                raise Exception("Unable to parse mutate output as json(" + str(e) "), it probably has syntax error:\n"+r)
            if not isinstance(patches, list):
                raise Exception("Invalid rule %s, evaluated to something that is not a list "% (mutate_rule["name"]))

            for p in patches:
                re.append(p)
        return re

    def mutate_k8s_request(self, request=None, request_path=""):
        re = {"uid": request["request"]["uid"]}
        response = {"response": re}
        if not self.is_allowed(request=request):
            rejected_reson = self.is_rejected(request=request)
            if rejected_reson:
                re["allowed"] = False
                re["status"] = {"message": str(rejected_reson)}

                return response

        re["allowed"] = True
        patchset = self.build_patchset(request=request, request_path=request_path)
        if len(patchset) > 0:
            patchset_str = json.dumps(patchset)
            re["patch"] = base64.b64encode(patchset_str.encode("utf-8")).decode("utf-8")
            re["patchType"] = "JSONPatch"
        return response

    def mutate_k8s_request_str(self, request_str, request_path=""):
        request = json.loads(request_str)
        resp = self.mutate_k8s_request(request=request, request_path=request_path)
        resp_str = json.dumps(resp)
        return resp_str
