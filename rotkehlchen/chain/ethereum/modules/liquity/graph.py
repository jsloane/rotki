QUERY_TROVE = (
    """
    troves(
        where: {
            owner_in: $addresses,
        }
    ){
        id
        debt
        owner {
            id
        }
        changes {
            id
            systemStateBefore {
                id
            }
            systemStateAfter {
                id
            }
            troveOperation
            debtAfter
            debtBefore
            debtChange
            collateralAfter
            collateralBefore
            collateralChange
            borrowingFee
            transaction{
                id
                blockNumber
                timestamp
            }
        }
    }
    }
    """
)

QUERY_STAKE = (
    """
        lqtyStakes(
            where: {
                id_in: $addresses,
            }
        ){
            id
            amount
            changes{
                transaction {
                    id
                    timestamp
                }
                stakeOperation
                stakedAmountAfter
                stakedAmountChange
                issuanceGain
                redemptionGain
            }
        }
    }
    """
)
