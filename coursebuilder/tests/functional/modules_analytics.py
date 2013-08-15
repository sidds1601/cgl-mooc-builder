# coding: utf-8
# Copyright 2013 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Tests for modules/dashboard/analytics."""

__author__ = 'Julia Oh(juliaoh@google.com)'

import os
import appengine_config

from controllers import sites
from controllers import utils
from models import config
from models import courses
from models import transforms

from models.progress import ProgressStats
from modules.dashboard import analytics


import actions
from actions import assert_contains
from actions import assert_does_not_contain
from actions import assert_equals


class ProgressAnalyticsTest(actions.TestBase):
    """Tests the progress analytics page on the Course Author dashboard."""

    def enable_progress_tracking(self):
        config.Registry.test_overrides[
            utils.CAN_PERSIST_ACTIVITY_EVENTS.name] = True

    def test_empty_student_progress_stats_analytics_displays_nothing(self):
        """Test analytics page on course dashboard when no progress stats."""

        # The admin looks at the analytics page on the board to check right
        # message when no progress has been recorded.

        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics')
        assert_contains(
            'Google &gt; Dashboard &gt; Analytics', response.body)
        assert_contains('have not been calculated yet', response.body)

        compute_form = response.forms['gcb-compute-student-stats']
        response = self.submit(compute_form)
        assert_equals(response.status_int, 302)
        assert len(self.taskq.GetTasks('default')) == 4

        response = self.get('dashboard?action=analytics')
        assert_contains('is running', response.body)

        self.execute_all_deferred_tasks()

        response = self.get('dashboard?action=analytics')
        assert_contains('were last updated at', response.body)
        assert_contains('currently enrolled: 0', response.body)
        assert_contains('total: 0', response.body)

        assert_contains('Student Progress Statistics', response.body)
        assert_contains(
            'No student progress has been recorded for this course.',
            response.body)
        actions.logout()

    def test_student_progress_stats_analytics_displays_on_dashboard(self):
        """Test analytics page on course dashboard."""

        self.enable_progress_tracking()

        student1 = 'student1@google.com'
        name1 = 'Test Student 1'
        student2 = 'student2@google.com'
        name2 = 'Test Student 2'

        # Student 1 completes a unit.
        actions.login(student1)
        actions.register(self, name1)
        actions.view_unit(self)
        actions.logout()

        # Student 2 completes a unit.
        actions.login(student2)
        actions.register(self, name2)
        actions.view_unit(self)
        actions.logout()

        # Admin logs back in and checks if progress exists.
        email = 'admin@google.com'
        actions.login(email, is_admin=True)
        response = self.get('dashboard?action=analytics')
        assert_contains(
            'Google &gt; Dashboard &gt; Analytics', response.body)
        assert_contains('have not been calculated yet', response.body)

        compute_form = response.forms['gcb-compute-student-stats']
        response = self.submit(compute_form)
        assert_equals(response.status_int, 302)
        assert len(self.taskq.GetTasks('default')) == 4

        response = self.get('dashboard?action=analytics')
        assert_contains('is running', response.body)

        self.execute_all_deferred_tasks()

        response = self.get('dashboard?action=analytics')
        assert_contains('were last updated at', response.body)
        assert_contains('currently enrolled: 2', response.body)
        assert_contains('total: 2', response.body)

        assert_contains('Student Progress Statistics', response.body)
        assert_does_not_contain(
            'No student progress has been recorded for this course.',
            response.body)
        # JSON code for the completion statistics.
        assert_contains(
            '\\"u.1.l.1\\": {\\"progress\\": 0, \\"completed\\": 2}',
            response.body)
        assert_contains(
            '\\"u.1\\": {\\"progress\\": 2, \\"completed\\": 0}',
            response.body)

    def test_get_entity_id_wrapper_in_progress_works(self):
        """Tests get_entity_id wrappers in progress.ProgressStats."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        unit1 = course.add_unit()

        # pylint: disable-msg=protected-access
        assert_equals(
            progress_stats._get_unit_ids_of_type_unit(), [unit1.unit_id])
        assessment1 = course.add_assessment()
        assert_equals(
            progress_stats._get_assessment_ids(), [assessment1.unit_id])
        lesson11 = course.add_lesson(unit1)
        lesson12 = course.add_lesson(unit1)
        assert_equals(
            progress_stats._get_lesson_ids(unit1.unit_id),
            [lesson11.lesson_id, lesson12.lesson_id])
        lesson11.has_activity = True
        course.set_activity_content(lesson11, u'var activity=[]', [])
        assert_equals(
            progress_stats._get_activity_ids(unit1.unit_id, lesson11.lesson_id),
            [0])
        assert_equals(
            progress_stats._get_activity_ids(unit1.unit_id, lesson12.lesson_id),
            [])

    def test_get_entity_label_wrapper_in_progress_works(self):
        """Tests get_entity_label wrappers in progress.ProgressStats."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        unit1 = course.add_unit()

        # pylint: disable-msg=protected-access
        assert_equals(
            progress_stats._get_unit_label(unit1.unit_id),
            'Unit %s' % unit1.index)
        assessment1 = course.add_assessment()
        assert_equals(
            progress_stats._get_assessment_label(assessment1.unit_id),
            assessment1.title)
        lesson11 = course.add_lesson(unit1)
        lesson12 = course.add_lesson(unit1)
        assert_equals(
            progress_stats._get_lesson_label(unit1.unit_id, lesson11.lesson_id),
            lesson11.index)
        lesson11.has_activity = True
        course.set_activity_content(lesson11, u'var activity=[]', [])
        assert_equals(
            progress_stats._get_activity_label(
                unit1.unit_id, lesson11.lesson_id, 0), 'L1.1')
        assert_equals(
            progress_stats._get_activity_label(
                unit1.unit_id, lesson12.lesson_id, 0), 'L1.2')
        lesson12.objectives = """
            <question quid="123" weight="1" instanceid=1></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="456" instanceid=2></question-group>
            yet_more_random_text
        """
        assert_equals(
            progress_stats._get_component_ids(
                unit1.unit_id, lesson12.lesson_id, 0), [u'1', u'2'])

    def test_compute_entity_dict_constructs_dict_correctly(self):
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        progress_stats = ProgressStats(course)
        course_dict = progress_stats.compute_entity_dict('course', [])
        assert_equals(course_dict, {
            'label': 'UNTITLED COURSE', 'u': {}, 's': {}})

    def test_compute_entity_dict_constructs_dict_for_empty_course_correctly(
        self):
        """Tests correct entity_structure is built."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])
        unit1 = course.add_unit()
        assessment1 = course.add_assessment()
        progress_stats = ProgressStats(course)
        # pylint: disable-msg=g-inconsistent-quotes
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {'label': 'UNTITLED COURSE', 'u': {unit1.unit_id: {
                'label': 'Unit %s' % unit1.index, 'l': {}}}, 's': {
                    assessment1.unit_id: {'label': assessment1.title}}})
        lesson11 = course.add_lesson(unit1)
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {
                "s": {
                    assessment1.unit_id: {
                        "label": assessment1.title
                    }
                },
                "u": {
                    unit1.unit_id: {
                        "l": {
                            lesson11.lesson_id: {
                                "a": {},
                                "h": {
                                    0: {
                                        "c": {},
                                        "label": "L1.1"
                                    }
                                },
                                "label": lesson11.index
                            }
                        },
                        "label": "Unit %s" % unit1.index
                    }
                },
                'label': 'UNTITLED COURSE'
            })
        lesson11.objectives = """
            <question quid="123" weight="1" instanceid="1"></question>
            random_text
            <gcb-youtube videoid="Kdg2drcUjYI" instanceid="VD"></gcb-youtube>
            more_random_text
            <question-group qgid="456" instanceid="2"></question-group>
            yet_more_random_text
        """
        assert_equals(
            progress_stats.compute_entity_dict('course', []),
            {
                "s": {
                    assessment1.unit_id: {
                        "label": assessment1.title
                    }
                },
                "u": {
                    unit1.unit_id: {
                        "l": {
                            lesson11.lesson_id: {
                                "a": {},
                                "h": {
                                    0: {
                                        "c": {
                                            u'1': {
                                                "label": "L1.1.1"
                                            },
                                            u'2': {
                                                "label": "L1.1.2"
                                            }
                                        },
                                        "label": "L1.1"
                                    }
                                },
                                "label": lesson11.index
                            }
                        },
                        "label": "Unit %s" % unit1.index
                    }
                },
                "label": 'UNTITLED COURSE'
            })


class QuestionAnalyticsTest(actions.TestBase):
    """Tests the question analytics page from Course Author dashboard."""

    def _enable_activity_tracking(self):
        config.Registry.test_overrides[
            utils.CAN_PERSIST_ACTIVITY_EVENTS.name] = True

    def test_get_summarized_question_list_from_event(self):
        """Tests the transform functions per event type."""
        sites.setup_courses('course:/test::ns_test, course:/:/')
        course = courses.Course(None, app_context=sites.get_all_courses()[0])

        question_aggregator = (
            analytics.ComputeQuestionStats.MultipleChoiceQuestionAggregator(
                course))

        event_payloads = open(os.path.join(
            appengine_config.BUNDLE_ROOT,
            'tests/unit/common/event_payloads.json')).read()

        event_payload_dict = transforms.loads(event_payloads)
        for event_info in event_payload_dict.values():
            # pylint: disable-msg=protected-access
            questions = question_aggregator._process_event(
                event_info['event_source'], event_info['event_data'])
            assert_equals(questions, event_info['transformed_dict_list'])

    def test_compute_question_stats_on_empty_course_returns_empty_dicts(self):

        sites.setup_courses('course:/test::ns_test, course:/:/')
        app_context = sites.get_all_courses()[0]

        question_stats_computer = analytics.ComputeQuestionStats(app_context)
        id_to_questions, id_to_assessments = question_stats_computer.run()
        assert_equals({}, id_to_questions)
        assert_equals({}, id_to_assessments)