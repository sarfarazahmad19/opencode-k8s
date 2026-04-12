import pytest


def pytest_addoption(parser):
    parser.addoption("--namespace", action="store", default="traefik")
    parser.addoption("--helmrelease", action="store", default="traefik")
    parser.addoption("--helmrelease-namespace", action="store", default="traefik")
