package dtcBattery {
    private import MetaModelDigitalTwin::*;

    #Component def BatteryStorage_Sensor { }
    #Component def BatteryExternalInput_Sensor { }

    // Local trigger only. The Lambda is a no-op placeholder (same as dtcGrid's
    // "greenEnergyUpdate"): it exists so fed-sysml can reference
    // "dtcBattery.plugDecision" and generate the Event Registry -> Step Function
    // -> Collector -> Strategy -> Feedback infrastructure. The charging decision
    // itself runs in the federation-owned Strategy Lambda - a twin-owned
    // NOFEEDBACK action has no way to write another twin.
    //
    // Named plugDecision (not plugUpdate) purely so it is distinguishable from
    // dtcCharger's plugUpdate in CloudWatch logs. The SSM registry keys are
    // namespaced per twin, so there would be no collision either way.
    #Condition def BatteryPlugDecisionStrategy {
        #strategyAction plugDecision :>> strategieActions {
            :>> name = "plugDecision";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/battery/decision-trigger";
            :>> external = false;
        }
    }

    // Second decision trigger: the PV surplus point. Reuses the same no-op
    // trigger Lambda - only the condition differs.
    //
    // Unlike every other condition in this project this one is NOT a
    // self-comparison: it compares generatedPower against a constant, so
    // event-checker fires it ONLY when the value actually equals the threshold.
    // That keeps ordinary PV pushes from starting a Step Function at all.
    #Condition def BatterySurplusStrategy {
        #strategyAction surplusDecision :>> strategieActions {
            :>> name = "surplusDecision";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/battery/decision-trigger";
            :>> external = false;
        }
    }

    // Third decision trigger: favourable renewable conditions in the grid. Same
    // no-op trigger Lambda, conditional like BatterySurplusStrategy - it fires
    // only when greenEnergyPercentage actually exceeds the threshold.
    #Condition def BatteryGreenEnergyStrategy {
        #strategyAction greenEnergyDecision :>> strategieActions {
            :>> name = "greenEnergyDecision";
            :>> strategyType = StrategyType::LAMBDA;
            :>> pathToCode = "/pipeline/code/microgrid/battery/decision-trigger";
            :>> external = false;
        }
    }

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
            // PV production level (kW) at which the battery treats generation as
            // a surplus and raises the EV charging power. This is the battery's
            // OWN threshold - it names no other twin, so dtcBattery stays
            // independent before federation.
            #constAttribute surplusThreshold {
                :>> value default "47.5";
                :>> dataType default AttributeDataType::DOUBLE;
            }
            // Share of renewables in the grid (%) above which the battery
            // prioritises storing that energy for itself and stops charging the
            // EV. Again the battery's OWN threshold - names no other twin.
            #constAttribute greenEnergyThreshold {
                :>> value default "70.0";
                :>> dataType default AttributeDataType::DOUBLE;
            }
            // The "plugged in" value, used as the right-hand side of the plug
            // condition so that it compares against a constant instead of
            // against itself. The Charger push Lambda normalises every plug
            // state to exactly "true"/"false", so this matches reliably.
            #constAttribute pluggedTrue {
                :>> value default "true";
                :>> dataType default AttributeDataType::STRING;
            }
        }

        :>> hotDatabaseRetentionDays default 30;
        :>> coldDatabaseRetentionDays default 30;

        // Fires on every new isPlugged value arriving from the Charger push
        // (self-comparison, always true - the project-wide idiom). This is the
        // ONLY decision trigger for now: the other inputs (generatedPower,
        // greenEnergyPercentage, maxPower, charge) are read by the Strategy
        // Lambda itself, so they do not need to be triggers and cannot amplify
        // the number of executions.
        //
        // NOFEEDBACK: the local action publishes nothing; the federation
        // Feedback Lambda writes actChargeEV to dtcCharger.
        #condition plugDecisionReport : BatteryPlugDecisionStrategy {
            :>> leftOperand = dtcBattery.storage.isPlugged;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = dtcBattery.pluggedTrue;
            :>> plugDecision {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                isPlugged :>> inputParameters = dtcBattery.storage.isPlugged;
            }
        }

        // Fires ONLY when generatedPower reaches the surplus threshold exactly.
        // Deliberately not a self-comparison: event-checker evaluates
        // generatedPower == 47.5, so an ordinary PV push (42.5, 45, 50, ...) is
        // simply false and starts nothing at all - no Step Function, no failed
        // executions, no extra chance to loop.
        #condition surplusReport : BatterySurplusStrategy {
            :>> leftOperand = dtcBattery.externalInputs.generatedPower;
            :>> operator = ComparisonOperator::EQUAL;
            :>> rightOperand = dtcBattery.surplusThreshold;
            :>> surplusDecision {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                generatedPower :>> inputParameters = dtcBattery.externalInputs.generatedPower;
            }
        }

        // Fires ONLY while the grid's renewable share is above the threshold.
        // Conditional like surplusReport - an ordinary greenEnergy push below 70%
        // evaluates to false and starts nothing.
        #condition greenEnergyReport : BatteryGreenEnergyStrategy {
            :>> leftOperand = dtcBattery.externalInputs.greenEnergyPercentage;
            :>> operator = ComparisonOperator::GREATER_THAN;
            :>> rightOperand = dtcBattery.greenEnergyThreshold;
            :>> greenEnergyDecision {
                :>> feedbackTopicType = FeedbackTopicType::NOFEEDBACK;
                greenEnergyPercentage :>> inputParameters = dtcBattery.externalInputs.greenEnergyPercentage;
            }
        }
    }
}
