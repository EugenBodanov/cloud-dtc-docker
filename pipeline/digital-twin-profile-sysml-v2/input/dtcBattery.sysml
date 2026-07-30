package dtcBattery {
    private import MetaModelDigitalTwin::*;

    #Component def BatteryStorage_Sensor { }
    #Component def BatteryExternalInput_Sensor { }

    #Twin def dtcBattery {
        #entity dtcBattery {
            // Internal battery state (measured at runtime). Same pattern as
            // dtc2bat's p16 component.
            #component storage : BatteryStorage_Sensor {
                // Current battery charge level, in percent (0-100).
                #measureAttribute charge {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
                // Whether the battery/charger connection is active ("true"/"false").
                #measureAttribute isPlugged {
                    :>> dataType default AttributeDataType::STRING;
                }
                // Current state: "charging" / "discharging" / "idle". Decided
                // internally by the battery (not written by any federation).
                #measureAttribute chargingStatus {
                    :>> dataType default AttributeDataType::STRING;
                }
            }
            // External inputs received from other twins via federation. Same
            // pattern as dtc2bat's pvInput virtual-sensor component - these are
            // written by push/request federations, not produced locally.
            #component externalInputs : BatteryExternalInput_Sensor {
                // From the PV twin.
                #measureAttribute generatedPower {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
                // From the Grid twin.
                #measureAttribute greenEnergyPercentage {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
                // From the Grid twin.
                #measureAttribute electricityPrice {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
                // Available external power - provided dynamically by Grid/PV/another
                // twin. NOT a battery constant (the battery does not know the
                // available external power).
                #measureAttribute maxPower {
                    :>> dataType default AttributeDataType::DOUBLE;
                }
            }
            // Static battery configuration (fixed specifications). Declared at the
            // #entity level - NOT inside a component - because the converter drops
            // #constAttribute nested in a component; entity-level consts materialize
            // as a generated const_component (same as dtc2bat's trueValue/maxTemp).
            // Default values are placeholders - adjust to the real battery spec.
            #constAttribute totalCapacity {
                :>> value default "100.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
            #constAttribute maxChargingPower {
                :>> value default "22.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
            #constAttribute maxDischargingPower {
                :>> value default "22.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
        }

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;
    }
}
