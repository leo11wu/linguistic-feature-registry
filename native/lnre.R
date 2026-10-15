args <- commandArgs(trailingOnly=TRUE)
library(zipfR)
tab <- read.table(file("stdin"), header=TRUE)
model <- if (length(args)) args[[1]] else "fzm"
stopifnot(model %in% c("fzm", "zm", "gigp"), nrow(tab)>=3, all(tab$m>0), all(tab$Vm>0))
spectrum <- spc(m=tab$m, Vm=tab$Vm)
set.seed(1729)
fit <- lnre(model, spectrum)
params <- fit$param
stopifnot(length(params)>0, all(is.finite(unlist(params))))
gof <- tryCatch({
  g <- lnre.goodness.of.fit(fit, spectrum, n.estimated=length(params))
  stopifnot(is.finite(g$X2[[1]]),is.finite(g$df[[1]]),g$df[[1]]>0,is.finite(g$p[[1]]))
  list(status="computed", method="zipfR multivariate chi-squared", chi_squared=g$X2[[1]],
       df=g$df[[1]], p_value=g$p[[1]],
       p_value_display=if (g$p[[1]]==0) "<1e-300" else format(g$p[[1]],digits=6),
       estimated_parameters=length(params), spectrum_m_max=g$df[[1]]+length(params)-1,
       note="same spectrum used for estimation; degrees of freedom corrected by zipfR")
}, error=function(e) list(status="unavailable", reason=conditionMessage(e)))
expected <- EVm(fit, m=tab$m, N=N(spectrum))
spectrum_rows <- lapply(seq_along(tab$m), function(i) list(frequency=tab$m[[i]],observed_types=tab$Vm[[i]],expected_types=expected[[i]]))
estimation <- list(seed=1729, observed_tokens=N(spectrum), observed_types=V(spectrum),
                   expected_types=EV(fit,N=N(spectrum)), expected_singletons=EVm(fit,m=1,N=N(spectrum)),
                   cost="zipfR default multivariate goodness of fit", package_version=as.character(packageVersion("zipfR")))
# A small base-R serializer avoids adding jsonlite to the separately managed runtime.
to_json <- function(x) {
  if (is.null(x)) return("null")
  if (is.list(x)) {
    named <- !is.null(names(x)) && all(nzchar(names(x)))
    values <- vapply(x,to_json,character(1))
    if (named) return(paste0("{",paste(paste0(vapply(names(x),encodeString,character(1),quote='"'),":",values),collapse=","),"}"))
    return(paste0("[",paste(values,collapse=","),"]"))
  }
  if (length(x)!=1) return(to_json(as.list(x)))
  if (is.na(x)) return("null")
  if (is.character(x)) return(encodeString(x,quote='"'))
  if (is.logical(x)) return(if (x) "true" else "false")
  if (!is.finite(x)) return("null")
  format(x,digits=17,scientific=TRUE,trim=TRUE)
}
cat(to_json(list(model=model, method="zipfR-0.6-70", parameters=params,
                 goodness_of_fit=gof, expected_spectrum=spectrum_rows, estimation=estimation)),"\n",sep="")
