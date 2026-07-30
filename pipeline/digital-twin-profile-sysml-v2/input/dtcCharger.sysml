package dtcCharger {
    private import MetaModelDigitalTwin::*;

    #Component def ChargerState_Sensor { }

    #Twin def dtcCharger {
        #entity dtcCharger {
            // Internal charger state. Same pattern as dtcBattery's storage
            // component.
            #component state : ChargerState_Sensor {
                // Whether the charger/battery connection is active ("true"/"false").
                #measureAttribute isPlugged {
                    :>> dataType default AttributeDataType::STRING;
                }
                // Charging power (kW) currently applied to the EV, sent by the
                // Battery twin via federation. Received and exposed only - NOT
                // calculated by the Charger.
                #measureAttribute actChargeEV {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
            // Maximum charging power the charger hardware can deliver, in kW.
            // Declared at #entity level (NOT inside a #component) because the
            // converter drops #constAttribute nested in a component; entity-level
            // consts materialize as a generated const_component (same as
            // dtc2bat's trueValue/maxTemp).
            #constAttribute maxPower {
                :>> value default "22.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
        }

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;
    }
}
