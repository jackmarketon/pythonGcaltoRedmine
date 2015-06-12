from datetime import datetime, timedelta
from time import time
from dateutil import parser
from apiclient import discovery
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import client, tools
from redmine import Redmine

import os, pprint, oauth2client, configparser

try:
	import argparse
	flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
	flags = None

class settings:
	def __init__(self):
		self.gcal_scopes = 'https://www.googleapis.com/auth/calendar.readonly'
		self.client_secret_file = 'client_secret.json'
		self.application_name = 'Calendar API'
		self.gcal_credentials = self.get_gcal_credentials()
		self.gcal_service = build('calendar', 'v3', http=self.gcal_credentials.authorize(Http()))

		Config = configparser.ConfigParser()
		Config.read('./config.ini')

		self.redmine_url = Config.get('redmine', 'url')
		self.redmine_user = Config.get('redmine', 'user')
		self.redmine_password = Config.get('redmine', 'pass')
		self.redmine = Redmine(self.redmine_url,
							   username=self.redmine_user,
							   password=self.redmine_password)

		self.activities = self.get_redmine_activities()
		self.projects = self.get_redmine_projects()

	def create_time_entry(self, event):
		self.redmine.time_entry.create(**event)

	def get_redmine_activities(self):
		activities = {}

		for enumeration in self.redmine.enumeration.filter(resource='time_entry_activities'):
			activities[enumeration._attributes['name']] = enumeration._attributes['id']

		return activities

	def get_redmine_projects(self):
		projects = {}

		for project in self.redmine.project.all():
			projects[project._attributes['name']] = project._attributes['id']

		return projects

	def get_gcal_credentials(self):
		home_dir = os.path.expanduser('~')
		credential_dir = os.path.join(home_dir, '.credentials')
		if not os.path.exists(credential_dir):
			os.makedirs(credential_dir)
		credential_path = os.path.join(credential_dir,
									   'calendar-api.json')

		store = oauth2client.file.Storage(credential_path)
		credentials = store.get()
		if not credentials or credentials.invalid:
			flow = client.flow_from_clientsecrets(self.client_secret_file,
												  self.gcal_scopes)
			flow.user_agent = self.application_name
			if flags:
				credentials = tools.run_flow(flow, store, flags)

			print('Storing credentials to ' + credential_path)
		return credentials

def get_todays_gcal(gcal_service):
	today = datetime.today();
	# 'Z' indicates UTC time
	timeMin = datetime(today.year, today.month, today.day)
	timeMax = datetime(today.year, today.month, today.day) + timedelta(days=1)

	eventResults = gcal_service.events().list(
		calendarId='primary',
		timeMin=timeMin.isoformat() + 'Z',
		timeMax=timeMax.isoformat() + 'Z',
		maxResults=100).execute()
	events = eventResults.get('items', [])

	if not events:
		print('No upcoming events found.')
	else:
		return events

def parse_time_event(event, settings):
	parsed_event = event.split(' - ')
	event_dict = {}

	if(len(parsed_event) == 3):

		if parsed_event[0].isdigit():
			event_dict['issue_id'] = parsed_event[0]
		elif parsed_event[0] in settings.projects:
			event_dict['project_id'] = settings.projects[parsed_event[0]]

		if parsed_event[1] in settings.activities:
			event_dict['activity_id'] = settings.activities[parsed_event[1]]

		if parsed_event[2]:
			event_dict['comments'] = parsed_event[2]

		# for key in event_dict:
		# 	print(str(key) + ": " + str(event_dict[key]))

		return event_dict
	else:
		return False

def main():
	s = settings()
	events = get_todays_gcal(s.gcal_service)

	if events:
		for event in events:
			# time_entry = s.redmine.time_entry.new()
			parsed_event = parse_time_event(event['summary'], s)

			if parsed_event is not False:
				event_start = parser.parse(event['start']['dateTime'])
				event_end = parser.parse(event['end']['dateTime'])
				event_time = event_end - event_start

				parsed_event['hours'] = event_time.total_seconds() / 3600

				s.create_time_entry(parsed_event)
				print('{}: {}'.format(parsed_event['hours'], event['summary']))

if __name__ == '__main__':
	main()