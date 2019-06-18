# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Utilities for managing issue tracker instance."""

from config import local_config
from datastore import data_types
from datastore import ndb_utils
from issue_management import monorail
from metrics import logs


def _get_issue_tracker_project_name(testcase=None):
  """Return issue tracker project name given a testcase or default."""
  from datastore import data_handler
  job_type = testcase.job_type if testcase else None
  return data_handler.get_issue_tracker_name(job_type)


def get_issue_tracker(project_name=None, use_cache=False):
  """Get the issue tracker with the given type and name."""
  issue_tracker_config = local_config.IssueTrackerConfig()
  if not project_name:
    from datastore import data_handler
    project_name = data_handler.get_issue_tracker_name()

  issue_project_config = issue_tracker_config.get(project_name)
  if not issue_project_config:
    raise ValueError('Issue tracker for {} does not exist'.format(project_name))

  if issue_project_config['type'] == 'monorail':
    return monorail.get_issue_tracker(project_name, use_cache=use_cache)

  raise ValueError('Invalid issue tracker type ' + issue_project_config['type'])


def get_issue_tracker_for_testcase(testcase, use_cache=False):
  """Get the issue tracker with the given type and name."""
  issue_tracker_project_name = _get_issue_tracker_project_name(testcase)
  if not issue_tracker_project_name:
    return None

  return get_issue_tracker(issue_tracker_project_name, use_cache=use_cache)


def get_issue_for_testcase(testcase):
  """Return issue object associated with testcase."""
  if not testcase.bug_information:
    return None

  issue_tracker = get_issue_tracker_for_testcase(testcase, use_cache=True)
  if not issue_tracker:
    return None

  try:
    issue_id = testcase.bug_information
    issue = issue_tracker.get_original_issue(issue_id)
  except:
    logs.log_error(
        'Error occurred when fetching issue %s.' % testcase.bug_information)
    return None

  return issue


def get_search_keywords(testcase):
  """Get search keywords for a testcase."""
  crash_state_lines = testcase.crash_state.splitlines()
  # Use top 2 frames for searching.
  return crash_state_lines[:2]


def get_similar_issues(issue_tracker, testcase, only_open=True):
  """Get issue objects that seem to be related to a particular test case."""
  # Get list of issues using the search query.
  keywords = get_search_keywords(testcase)

  issues = issue_tracker.find_issues(keywords=keywords, only_open=only_open)
  issue_ids = [issue.id for issue in issues]

  # Add issues from similar testcases sharing the same group id.
  if testcase.group_id:
    group_query = data_types.Testcase.query(
        data_types.Testcase.group_id == testcase.group_id)
    similar_testcases = ndb_utils.get_all_from_query(group_query)
    for similar_testcase in similar_testcases:
      if not similar_testcase.bug_information:
        continue

      # Exclude issues already added above from search terms.
      issue_id = int(similar_testcase.bug_information)
      if issue_id in issue_ids:
        continue

      # Get issue object using ID.
      issue = issue_tracker.get_issue(issue_id)
      if not issue:
        continue

      # If our search criteria allows open bugs only, then check issue and
      # testcase status so as to exclude closed ones.
      if (only_open and (not issue.is_open or not testcase.open)):
        continue

      issues.append(issue)
      issue_ids.append(issue_id)

  return issues


def get_similar_issues_url(issue_tracker, testcase, only_open=True):
  """Get similar issues web URL."""
  keywords = get_search_keywords(testcase)
  return issue_tracker.find_issues_url(keywords=keywords, only_open=only_open)


def get_issue_url(testcase):
  """Return issue url for a testcase."""
  issue_tracker = get_issue_tracker_for_testcase(testcase)
  if not issue_tracker or not testcase.bug_information:
    return None

  return issue_tracker.issue_url(testcase.bug_information)


def was_label_added(issue, label):
  """Check if a label was ever added to an issue."""
  for action in issue.actions:
    for added in action.labels.added:
      if label.lower() == added.lower():
        return True

  return False
