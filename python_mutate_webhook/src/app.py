import deps
import base64
import copy
import http
import json
import random
import jsonpatch
from flask import Flask, jsonify, request
from mutate_test import MutatingWebhook
from pathlib import Path

app = Flask(__name__)

# @app.route("/validate", methods=["POST"])
# def validate():
#     allowed = True
#     try:
#         for container_spec in request.json["request"]["object"]["spec"]["containers"]:
#             if "env" in container_spec:
#                 allowed = False
#     except KeyError:
#         pass
#     return jsonify(
#         {
#             "response": {
#                 "allowed": allowed,
#                 "uid": request.json["request"]["uid"],
#                 "status": {"message": "env keys are prohibited"},
#             }
#         }
#     )


def find_rule_dir():
    base_dir = Path(__file__).resolve().parents[0]
    return str(base_dir.joinpath("rule"))


def init_mutatingwebhook():
    MutatingWebhook(admission_dir=find_rule_dir())


@app.route("/mutate", methods=["POST"])
def mutate():
    # spec = request.json["request"]["object"]
    # modified_spec = copy.deepcopy(spec)
    mw = MutatingWebhook(admission_dir=find_rule_dir())

    try:
        modified_spec["metadata"]["labels"]["example.com/new-label"] = str(
            random.randint(1, 1000)
        )
    except KeyError:
        pass
    patch = jsonpatch.JsonPatch.from_diff(spec, modified_spec)
    return jsonify(
        {
            "response": {
                "allowed": True,
                "uid": request.json["request"]["uid"],
                "patch": base64.b64encode(str(patch).encode()).decode(),
                "patchtype": "JSONPatch",
            }
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return ("", http.HTTPStatus.NO_CONTENT)


if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)  # pragma: no cover