
# Copyright 2017-present Open Networking Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from synchronizers.new_base.modelaccessor import VOLTServiceInstance, ServiceInstanceLink, ONUDevice, ServiceInstance, model_accessor
from synchronizers.new_base.policy import Policy

class VOLTServiceInstancePolicy(Policy):
    model_name = "VOLTServiceInstance"

    def handle_create(self, si):
        return self.handle_update(si)

    def handle_update(self, si):

        if (si.link_deleted_count > 0) and (not si.provided_links.exists()):
            # If this instance has no links pointing to it, delete
            self.handle_delete(si)
            if VOLTServiceInstance.objects.filter(id=si.id).exists():
                si.delete()
            return

        self.create_eastbound_instance(si)
        self.associate_onu_device(si)

    def handle_delete(self, si):
        pass

    def create_eastbound_instance(self, si):

        chain = si.subscribed_links.all()

        # Already has a chain
        if len(chain) > 0 and not si.is_new:
            self.logger.debug("MODEL_POLICY: VOLTServiceInstance %s is already part of a chain" % si.id)
            return

        # if it does not have a chain,
        # Find links to the next element in the service chain
        # and create one

        links = si.owner.subscribed_dependencies.all()

        for link in links:
            # SEBA-216 prevent any attempt to create an ONOSServiceInstance
            if "onos" in link.provider_service.name.lower():
                continue

            si_class = link.provider_service.get_service_instance_class_name()
            self.logger.info("MODEL_POLICY: VOLTServiceInstance %s creating %s" % (si, si_class))

            eastbound_si_class = model_accessor.get_model_class(si_class)
            eastbound_si = eastbound_si_class()
            eastbound_si.owner_id = link.provider_service_id
            eastbound_si.save()
            link = ServiceInstanceLink(provider_service_instance=eastbound_si, subscriber_service_instance=si)
            link.save()

    def associate_onu_device(self, si):

        self.logger.debug("MODEL_POLICY: attaching ONUDevice to VOLTServiceInstance %s" % si.id)

        base_si = ServiceInstance.objects.get(id=si.id)
        try:
            onu_device_serial_number = base_si.get_westbound_service_instance_properties("onu_device")
        except Exception as e:
            raise Exception(
                "VOLTServiceInstance %s has no westbound ServiceInstance specifying the onu_device, you need to manually specify it" % self.id)

        try:
            onu = ONUDevice.objects.get(serial_number=onu_device_serial_number)
        except IndexError:
            raise Exception("ONUDevice with serial number %s can't be found" % onu_device_serial_number)

        si.onu_device_id = onu.id
        si.save()
